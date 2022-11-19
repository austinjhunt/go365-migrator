from django.forms import Form, CharField, PasswordInput, TextInput


class SignupForm(Form):
    """ custom sign up form; overwrite specific properties of UsercreationForm 
    (css classes) """
    password1 = CharField(
        label="Password",
        widget=PasswordInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Password', 'id': 'signupPassword'}
        ))
    password2 = CharField(
        label="Password confirmation",
        widget=PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Password Confirmation',
                   'id': 'signupPasswordConfirm'}
        ),
        help_text="Enter the same password as above, for verification."
    )

    username = CharField(
        max_length=254,
        label="Username",
        widget=TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Username', 'id': 'signupUsername'}
        ))


class LoginForm(Form):
    """
    Custom login form, overwrites specific properties of AuthenticationForm 
    (css classes)
    """
    username = CharField(
        label="Username",

        widget=TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Username', 'id': 'loginUsername'},
        ))
    password = CharField(
        label="Password",
        widget=PasswordInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Password', 'id': 'loginPassword'}
        ))
