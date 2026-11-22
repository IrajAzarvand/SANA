from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("decoder_discovery", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="PublishedDecoderVersion"),
        migrations.DeleteModel(name="CandidateTestRun"),
        migrations.DeleteModel(name="DecoderCandidate"),
        migrations.DeleteModel(name="DiscoveryCase"),
        migrations.DeleteModel(name="ReferenceSource"),
    ]
