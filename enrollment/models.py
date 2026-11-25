from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal


def get_circular_storage():
    """Use Cloudinary raw storage for PDF circulars when configured, else default local storage."""
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary_storage.storage import RawMediaCloudinaryStorage
        return RawMediaCloudinaryStorage()
    from django.core.files.storage import default_storage
    return default_storage

class District(models.Model):
    name = models.CharField(max_length=100, default='Sangareddy')
    code = models.CharField(max_length=20, default='SRD', unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Mandal(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='mandals')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_schools(self):
        return self.schools.count()

    @property
    def enrolled_students_count(self):
        return Student.objects.filter(school__mandal=self).count()


class SchoolType(models.TextChoices):
    COED_HIGH = 'COED_HIGH', 'Co-ed High School (Classes 6-9, Scouts & Guides)'
    GIRLS_HIGH = 'GIRLS_HIGH', 'Girls High School (Classes 6-9, Guides only)'
    BOYS_HIGH = 'BOYS_HIGH', 'Boys High School (Classes 6-9, Scouts only)'
    PRIMARY = 'PRIMARY', 'Primary School (Classes 3-5, Cubs & Bulbuls)'
    UPPER_PRIMARY = 'UPPER_PRIMARY', 'Upper Primary School (Classes 6-7, Cubs & Bulbuls)'


class School(models.Model):
    udise_code = models.CharField(max_length=11, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    mandal = models.ForeignKey(Mandal, on_delete=models.CASCADE, related_name='schools')
    school_type = models.CharField(max_length=30, choices=SchoolType.choices, default=SchoolType.COED_HIGH)
    boys_quota = models.PositiveIntegerField(default=16)
    girls_quota = models.PositiveIntegerField(default=16)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='school_profile', null=True, blank=True)
    must_change_password = models.BooleanField(default=True)
    default_password = models.CharField(max_length=128, default='BSG@Sangareddy2026')
    is_sanctioned = models.BooleanField(default=True, db_index=True)
    sanction_order_number = models.CharField(max_length=100, blank=True, default='BSG/SRD/SANCTION/2026')
    headmaster_name = models.CharField(max_length=120, blank=True)
    contact_person = models.CharField(max_length=120, blank=True)
    contact_mobile = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.udise_code})"

    @property
    def display_name(self):
        # In case school names are duplicate across mandals, append mandal
        duplicate = School.objects.filter(name=self.name).exclude(pk=self.pk).exists()
        if duplicate:
            return f"{self.name} - {self.mandal.name}"
        return self.name

    def allowed_classes(self):
        if self.school_type in [SchoolType.COED_HIGH, SchoolType.GIRLS_HIGH, SchoolType.BOYS_HIGH]:
            return [6, 7, 8, 9]
        elif self.school_type == SchoolType.PRIMARY:
            return [3, 4, 5]
        elif self.school_type == SchoolType.UPPER_PRIMARY:
            return [6, 7]
        return [6, 7, 8, 9]

    def allowed_genders(self):
        if self.school_type == SchoolType.GIRLS_HIGH:
            return ['GIRL']
        elif self.school_type == SchoolType.BOYS_HIGH:
            return ['BOY']
        return ['BOY', 'GIRL']

    def allowed_units(self):
        if self.school_type == SchoolType.COED_HIGH:
            return ['Scouts (Boys)', 'Guides (Girls)']
        elif self.school_type == SchoolType.GIRLS_HIGH:
            return ['Guides (Girls)']
        elif self.school_type == SchoolType.BOYS_HIGH:
            return ['Scouts (Boys)']
        elif self.school_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY]:
            return ['Cubs (Boys)', 'Bulbuls (Girls)']
        return ['Scouts & Guides']

    def allowed_uniform_sizes(self):
        if self.school_type == SchoolType.PRIMARY:
            return ['24', '26', '28', '30', '32', '34']
        return ['28', '30', '32', '34', '36', '38', '40']

    def allowed_leader_sizes(self):
        return ['36', '38', '40', '42', '44', '46', '48']

    def allowed_leader_roles(self):
        if self.school_type == SchoolType.GIRLS_HIGH:
            return [LeaderRole.GUIDE_CAPTAIN]
        elif self.school_type == SchoolType.BOYS_HIGH:
            return [LeaderRole.SCOUT_MASTER]
        elif self.school_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY]:
            return [LeaderRole.CUB_MASTER, LeaderRole.FLOCK_LEADER]
        return [LeaderRole.SCOUT_MASTER, LeaderRole.GUIDE_CAPTAIN]

    def max_leaders_count(self):
        if self.school_type in [SchoolType.GIRLS_HIGH, SchoolType.BOYS_HIGH]:
            return 1
        return 2

    def boys_enrolled_count(self):
        return self.students.filter(gender='BOY').count()

    def girls_enrolled_count(self):
        return self.students.filter(gender='GIRL').count()

    def total_enrolled_count(self):
        return self.students.count()

    def total_quota(self):
        return self.boys_quota + self.girls_quota

    def has_recovery_contact(self):
        """Checks if school has at least one valid 10-digit phone number (HM or any Unit Leader)."""
        if self.contact_mobile:
            cleaned = ''.join(c for c in self.contact_mobile if c.isdigit())
            if len(cleaned) >= 10:
                return True
        for ul in self.unit_leaders.all():
            if ul.mobile:
                cleaned = ''.join(c for c in ul.mobile if c.isdigit())
                if len(cleaned) >= 10:
                    return True
        return False

    def boys_remaining_quota(self):
        return max(0, self.boys_quota - self.boys_enrolled_count())

    def girls_remaining_quota(self):
        return max(0, self.girls_quota - self.girls_enrolled_count())

    def is_quota_full(self, gender):
        if gender == 'BOY':
            return self.boys_enrolled_count() >= self.boys_quota
        elif gender == 'GIRL':
            return self.girls_enrolled_count() >= self.girls_quota
        return True


class StudentDetailLevel(models.TextChoices):
    SHORT = 'SHORT', 'Short Details'
    BRIEF = 'BRIEF', 'Brief Details (Tailoring Measurements)'


class Student(models.Model):
    GENDER_CHOICES = [
        ('BOY', 'Boy'),
        ('GIRL', 'Girl'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, db_index=True)
    name = models.CharField(max_length=120, db_index=True)
    father_name = models.CharField(max_length=120)
    class_level = models.IntegerField(db_index=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1)
    uniform_size = models.CharField(max_length=10)
    shoe_size = models.CharField(max_length=10)
    detail_level = models.CharField(
        max_length=10,
        choices=StudentDetailLevel.choices,
        default=StudentDetailLevel.SHORT,
        db_index=True
    )

    # BRIEF fields
    dob = models.DateField(null=True, blank=True)
    parent_mobile = models.CharField(max_length=15, null=True, blank=True)

    # Boys measurements (inches, 0.5 increments accepted)
    chest = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    waist = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    neck = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    shoulder = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    sleeve = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    shirt_length = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pant_length = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    # Girls measurements (inches, 0.5 increments accepted)
    bust = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    hip = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    kameez_length = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    salwar_length = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['class_level', 'gender', 'name']
        indexes = [
            models.Index(fields=['school', 'gender']),
            models.Index(fields=['school', 'class_level']),
            models.Index(fields=['school', 'detail_level']),
        ]

    def __str__(self):
        return f"{self.name} - Class {self.class_level} ({self.get_gender_display()})"

    @property
    def is_brief(self):
        return self.detail_level == StudentDetailLevel.BRIEF

    def clean(self):
        # Validate school gender allowance
        if self.gender not in self.school.allowed_genders():
            raise ValidationError(f"This school type ({self.school.get_school_type_display()}) cannot enroll {self.get_gender_display()}s.")

        # Validate class
        if self.class_level not in self.school.allowed_classes():
            raise ValidationError(f"Class {self.class_level} is not valid for this school type. Allowed: {self.school.allowed_classes()}")

        # Validate height range
        if self.height_cm < 90 or self.height_cm > 220:
            raise ValidationError("Height must be a plausible value between 90 cm and 220 cm.")

        # Validate half-step measurements
        measurement_fields = [
            'chest', 'waist', 'neck', 'shoulder', 'sleeve', 'shirt_length', 'pant_length',
            'bust', 'hip', 'kameez_length', 'salwar_length'
        ]
        for field_name in measurement_fields:
            val = getattr(self, field_name)
            if val is not None:
                if float(val) < 10 or float(val) > 60:
                    raise ValidationError(f"Measurement for {field_name} ({val} inches) is outside plausible range (10-60 inches).")
                # Check 0.5 step
                if (float(val) * 10) % 5 != 0:
                    raise ValidationError(f"Measurement {field_name} ({val}) must be in whole or 0.5 increments.")


class LeaderRole(models.TextChoices):
    SCOUT_MASTER = 'SCOUT_MASTER', 'Scout Master (Male, High School)'
    GUIDE_CAPTAIN = 'GUIDE_CAPTAIN', 'Guide Captain (Female, High School)'
    CUB_MASTER = 'CUB_MASTER', 'Cub Master (Male, Primary)'
    FLOCK_LEADER = 'FLOCK_LEADER', 'Flock Leader (Female, Primary)'


class UnitLeader(models.Model):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='unit_leaders')
    role = models.CharField(max_length=30, choices=LeaderRole.choices)
    name = models.CharField(max_length=120)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    mobile = models.CharField(max_length=15, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    is_frozen = models.BooleanField(default=True)
    email = models.EmailField(blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    shoe_size = models.CharField(max_length=10, blank=True)
    uniform_size = models.CharField(max_length=10, blank=True)
    chest_bust = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    waist = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    neck = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    shoulder = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    sleeve = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    top_length = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    bottom_length = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    hip = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role', 'name']

    def __str__(self):
        return f"{self.name} - {self.get_role_display()}"


class AuditLog(models.Model):
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=60)
    target_type = models.CharField(max_length=60)
    target_id = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    ip_address = models.CharField(max_length=45, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.action} - {self.description[:40]}"


class DistrictNotice(models.Model):
    title = models.CharField(max_length=200)
    title_te = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    content_te = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Circular(models.Model):
    title = models.CharField(max_length=200)
    reference_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='circulars/', storage=get_circular_storage)
    issued_date = models.DateField()
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_date', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.issued_date})"


class GalleryPhoto(models.Model):
    event_name = models.CharField(max_length=120, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    event_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='gallery/')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-event_date', '-created_at']

    def __str__(self):
        return f"{self.event_name} - {self.title or 'Photo'}"
