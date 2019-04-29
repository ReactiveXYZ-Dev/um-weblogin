# UM-Weblogin
A simple python interface that allows you to login into UM's web resources (Lecture recording, Wolverine Access, Canvas etc) programmtically, 
so you can write more cool stuff that leverage those resources.

## Features
* Simple API
* Supports both legacy weblogin and **Duo**

## Usage 
Simply import the <i>auth.py</i> into your project

### Make an authenticator
```python
from auth import Authenticator
auth = Authenticator()
```

The <i>Authenticator</i> class takes 3 optional arguments:

* two_fa: whether to use Duo 2fa for this authentication. Default True

* duo_factor_handler: a customizable callback/lambda function that takes available Duo factors and makes a choice. The handler will be fed in a list of dictionaries, each dictionary has a <i>device_name</i> key and a <i>factors</i> list, you need to return a tuple <i>(device_name, factor)</i> indicating your selection. Default a command line prompt for user to pick the factor.

* passcode_factor_handler: a customizable callback/lambda function that spits out a passcode string that is fed to Duo for the **passcode** factor. Default a command line prompt for user to enter the passcode.

### Authenticate
```python
auth.set_credentials(uniqname, password)
auth.authenticate()
```

Yep! That's it :) The entire login flow will be simulated automatically using either command line prompts or your custom handler defined above.

Now you have a fully authenticated [Requests](http://docs.python-requests.org/en/master/) object that you can mess around with!

```python
# get lecture recordings!
print(auth.session().get("https://leccap.engin.umich.edu/leccap/"))
```

### Development
Please post a issue or pull request if you see bugs or have any suggestions :)

### TODOs
* Canvas and some other external services use an additional layer of SAML authentication, but should be completely automate-able.
* It'd be awesome to be able to also accept Duo requests automatically, but can introduce a security concern (You know, some other guy can just log into your account automatically, which breaks the purpose of 2fa already). Still, nice to have as a potential on/off feature.
