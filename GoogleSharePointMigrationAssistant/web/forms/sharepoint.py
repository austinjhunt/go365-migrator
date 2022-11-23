from django.forms import CharField, TextInput, Form

class SharePointSiteSearchForm(Form):
    """
    Custom login form, overwrites specific properties of AuthenticationForm 
    (css classes)
    """
    site_name = CharField(
        label="Search for a SharePoint Online site (by its name) to which you have edit access",
        widget=TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Site Name', 'id': 'siteName'},
        ))

