from django.db import migrations


def synchronize_user_roles_and_admin_flags(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    database = schema_editor.connection.alias

    role_account_types = {
        'site_admin': 'admin',
        'main_user': 'organization',
        'branch_manager': 'organization',
        'personal_user': 'personal',
    }

    for role, account_type in role_account_types.items():
        is_site_admin = role == 'site_admin'
        User.objects.using(database).filter(role=role).update(
            account_type=account_type,
            is_staff=is_site_admin,
            is_superuser=is_site_admin,
        )

    # Unknown/legacy roles must never retain Django admin privileges.
    User.objects.using(database).exclude(
        role__in=tuple(role_account_types)
    ).update(is_staff=False, is_superuser=False)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0007_user_archival'),
    ]

    operations = [
        migrations.RunPython(
            synchronize_user_roles_and_admin_flags,
            migrations.RunPython.noop,
        ),
    ]
