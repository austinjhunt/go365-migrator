from django.views.generic import View 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from ..models import Migration
from ..plumbing.migrationassistant import scan_data_source


class ScanSourceDataView(View, LoginRequiredMixin):
    def get(self, request):
        migration_source = request.session.get('source_selected')
        migration_source_type = migration_source['source_type']
        del migration_source['source_type']
        migration_destination = request.session.get('destination_selected')
        migration_destination_details = list(migration_destination.values())[0]
        migration_destination_type = list(migration_destination.keys())[0]
        migration = Migration(
            user = request.user, 
            google_source = {
                'type': migration_source_type,
                'details': migration_source
            },
            local_temp_dir = request.user.username,
            target = {
                'type': migration_destination_type,
                'details': migration_destination_details
            }
        )
        migration.save()
        # async invocation of celery task
        scan_data_source.delay(
            migration_id=migration.id, 
            google_credentials=request.session.get('google_credentials'), 
            user_id=request.user.id
        )
        return redirect('list-migrations')


class ScanSourceReportView(View, LoginRequiredMixin):
    def get(self, request, migration_id):
        migration = Migration.objects.get(id=migration_id)
        if migration.user == request.user:
            return render(
                request=request,
                template_name='migrations/scan-report.html',
                context={
                    'migration': migration
                }
            )
        else:
            return redirect('list-migrations')