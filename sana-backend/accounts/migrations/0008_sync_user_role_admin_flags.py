from django.db import migrations
from django.utils import timezone


def synchronize_user_roles_and_admin_flags(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    database = schema_editor.connection.alias

    users = User.objects.using(database)
    if users.exists() and not users.filter(
        role='site_admin', is_active=True, archived_at__isnull=True
    ).exists():
        raise RuntimeError(
            'Role synchronization aborted: no active, non-archived site_admin account exists.'
        )

    UserSession = apps.get_model('accounts', 'UserSession')

    # Archived accounts must remain unable to authenticate even if legacy data
    # accidentally left is_active=True.
    archived_active_ids = list(
        users.filter(
            archived_at__isnull=False, is_active=True
        ).values_list('pk', flat=True)
    )
    if archived_active_ids:
        UserSession.objects.using(database).filter(
            user_id__in=archived_active_ids,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        users.filter(pk__in=archived_active_ids).update(is_active=False)
    role_account_types = {
        'site_admin': 'admin',
        'main_user': 'organization',
        'branch_manager': 'organization',
        'personal_user': 'personal',
    }

    for role, account_type in role_account_types.items():
        role_users = users.filter(role=role)
        account_type_changed_ids = list(
            role_users.exclude(account_type=account_type).values_list('pk', flat=True)
        )
        if account_type_changed_ids:
            UserSession.objects.using(database).filter(
                user_id__in=account_type_changed_ids,
                revoked_at__isnull=True,
            ).update(revoked_at=timezone.now())

        is_site_admin = role == 'site_admin'
        role_users.update(
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
