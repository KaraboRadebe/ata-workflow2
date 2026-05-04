import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TRFRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("project_name", models.CharField(max_length=255)),
                ("training_start", models.DateField()),
                ("status", models.CharField(
                    choices=[
                        ("DRAFT", "Draft"),
                        ("PENDING_L2", "Pending L2"),
                        ("PENDING_L3", "Pending L3"),
                        ("APPROVED", "Approved"),
                        ("REJECTED", "Rejected"),
                        ("REMEDIATION", "Remediation"),
                    ],
                    default="DRAFT",
                    max_length=20,
                )),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("remediated_at", models.DateTimeField(blank=True, null=True)),
                ("previous_snapshot", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("submitted_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="trf_submissions",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name="Milestone",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("target_date", models.DateField()),
                ("trf", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="milestones",
                    to="trf.trfrequest",
                )),
            ],
        ),
        migrations.CreateModel(
            name="Expense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("line_item_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("trf", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="expenses",
                    to="trf.trfrequest",
                )),
            ],
        ),
        migrations.CreateModel(
            name="TRFApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.IntegerField(choices=[(2, "Level 2"), (3, "Level 3")])),
                ("action", models.CharField(
                    choices=[("APPROVED", "Approved"), ("REJECTED", "Rejected")],
                    max_length=10,
                )),
                ("reason", models.TextField(blank=True)),
                ("acted_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to=settings.AUTH_USER_MODEL,
                )),
                ("trf", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="approvals",
                    to="trf.trfrequest",
                )),
            ],
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=50)),
                ("from_status", models.CharField(max_length=20)),
                ("to_status", models.CharField(max_length=20)),
                ("reason", models.TextField(blank=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to=settings.AUTH_USER_MODEL,
                )),
                ("trf", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="audit_events",
                    to="trf.trfrequest",
                )),
            ],
            options={"ordering": ["timestamp"]},
        ),
        migrations.CreateModel(
            name="ApproverProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.IntegerField(choices=[(2, "Level 2"), (3, "Level 3")])),
                ("is_available", models.BooleanField(default=True)),
                ("delegate", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="delegating_to",
                    to="trf.approverprofile",
                )),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="approver_profile",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name="NotificationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(
                    choices=[("EMAIL", "Email"), ("SLACK", "Slack"), ("IN_APP", "In-App")],
                    max_length=10,
                )),
                ("recipient", models.CharField(max_length=255)),
                ("result", models.CharField(
                    choices=[("SUCCESS", "Success"), ("FAILURE", "Failure")],
                    max_length=10,
                )),
                ("error_msg", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                ("trf", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="notification_logs",
                    to="trf.trfrequest",
                )),
            ],
        ),
    ]
