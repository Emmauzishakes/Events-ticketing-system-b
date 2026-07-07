# from django.contrib import admin
# from django.contrib.auth.models import Group
# from .models import CreatorApplication

# @admin.register(CreatorApplication)
# class CreatorApplicationAdmin(admin.ModelAdmin):
#     list_display = ('brand_name', 'user_email', 'phone_number', 'status', 'created_at')
#     list_filter = ('status', 'created_at')
#     search_fields = ('brand_name', 'user__username', 'user__email', 'phone_number', 'national_id_passport')
    
#     # Custom automated admin actions!
#     actions = ['approve_applications', 'reject_applications']

#     def user_email(self, obj):
#         """Helper to show the applicant's account email in the table column."""
#         return obj.user.email
#     user_email.short_description = 'User Email'

#     @admin.action(description='Approve selected creator applications')
#     def approve_applications(self, request, queryset):
#         """
#         Custom action to batch-approve creators, switch their status,
#         and handle group assignment or signals if needed.
#         """
#         updated_count = queryset.filter(status='PENDING').update(status='APPROVED')
        
#         # Optional: If you want to put approved creators into a Django Permission Group,
#         # you can iterate through the queryset and assign them here:
#         # creator_group, _ = Group.objects.get_or_create(name='Verified Creators')
#         # for app in queryset.filter(status='APPROVED'):
#         #     app.user.groups.add(creator_group)

#         self.message_user(
#             request, 
#             f"Successfully approved {updated_count} pending creator application(s)."
#         )

#     @admin.action(description='Reject selected creator applications (Mark Pending)')
#     def reject_applications(self, request, queryset):
#         """Marks applications as rejected."""
#         updated_count = queryset.filter(status='PENDING').update(status='REJECTED')
#         self.message_user(
#             request, 
#             f"Successfully marked {updated_count} pending creator application(s) as Rejected."
#         )