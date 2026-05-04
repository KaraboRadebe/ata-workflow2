from django.db import migrations


APPROVERS = [
    # (username, first_name, email, level)
    ("aidan",   "Aidan",   "aidan@ata.com",   2),
    ("trevor",  "Trevor",  "trevor@ata.com",  2),
    ("tasneem", "Tasneem", "tasneem@ata.com", 2),
    ("sharona", "Sharona", "sharona@ata.com", 3),
    ("melisa",  "Melisa",  "melisa@ata.com",  3),
    ("andre",   "Andre",   "andre@ata.com",   3),
]


def seed_approvers(apps, schema_editor):
    from django.contrib.auth.hashers import make_password
    User = apps.get_model("users", "User")
    ApproverProfile = apps.get_model("trf", "ApproverProfile")

    for username, first_name, email, level in APPROVERS:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first_name,
                "email": email,
                "role": "Admin",
                "is_active": True,
                "password": make_password("changeme123"),
            },
        )

        ApproverProfile.objects.get_or_create(
            user=user,
            defaults={"level": level, "is_available": True},
        )


def unseed_approvers(apps, schema_editor):
    User = apps.get_model("users", "User")
    usernames = [u for u, *_ in APPROVERS]
    User.objects.filter(username__in=usernames).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("trf", "0001_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_approvers, reverse_code=unseed_approvers),
    ]
