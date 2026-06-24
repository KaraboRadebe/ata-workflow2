from django.db import migrations, models
from procurement.stock_models import pod_upload_path


class Migration(migrations.Migration):

    dependencies = [
        ('procurement', '0005_add_certification_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proofofdelivery',
            name='pod_file',
            field=models.FileField(blank=True, null=True, upload_to=pod_upload_path),
        ),
        migrations.AddField(
            model_name='proofofdelivery',
            name='signature_data',
            field=models.TextField(blank=True, default='', help_text='Base64-encoded signature image data'),
        ),
    ]
