import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banktransfer_custom', '0013_paymentproof'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bankimportjob',
            name='event',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='banktransfer_custom_import_jobs', to='pretixbase.event'),
        ),
        migrations.AlterField(
            model_name='bankimportjob',
            name='organizer',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='banktransfer_custom_import_jobs', to='pretixbase.organizer'),
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='event',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='banktransfer_custom_transactions', to='pretixbase.event'),
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='organizer',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='banktransfer_custom_transactions', to='pretixbase.organizer'),
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='import_job',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='banktransfer_custom_transactions', to='banktransfer_custom.bankimportjob'),
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='banktransfer_custom_transactions', to='pretixbase.order'),
        ),
    ]
