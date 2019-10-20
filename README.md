# UM-Weblogin
A simple python interface that allows you to login into UM's web resources (Lecture recording, Wolverine Access, Canvas etc) programmtically, 
so you can write more cool stuff that leverage those resources.

## Features
* Simple API
* Supports both legacy weblogin and **Duo**

## Usage 
Simply import <i>auth.py</i> into your project

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

Now you have a fully authenticated [requests](https://requests.kennethreitz.org/en/master/) object that you can mess around with!

```python
# get lecture recordings!
print(auth.session().get("https://leccap.engin.umich.edu/leccap/"))
```

### Advanced example
With an authenticated requests session, although it's now very straightfoward to access U-M resources (e.g. lecture recording, mcommunity etc), it requires just a little bit more effort to be able to access third party sites that uses U-M SSO and SAML to log into their sites (e.g. Canvas). In this example, I will show you how to use your U-M session to get into your personal canvas page:

```python
from auth import Authenticator
from bs4 import BeautifulSoup

# UM Authentication
def auto_select(factors):
    """
    automatically select your first device and first auth factor
    """
    first = factors[0]
    return (first['device_name'], first['factors'][0])

authenticator = Authenticator(duo_factor_handler=auto_select)
authenticator.set_credentials('YOUR UNIQUE NAME', 'YOUR PASSWORD')
authenticator.authenticate()

# Now your have an U-M session
session = authenticator.session()

# Canvas Authentication
html = session.get('https://umich.instructure.com/login/saml').text
html = BeautifulSoup(html, 'html.parser')
saml_input = html.find(attrs={"name": "SAMLResponse"})
saml_id = saml_input['value']

# Post SAML response to Canvas...
session.post('https://umich.instructure.com/login/saml', data={'SAMLResponse': saml_id})

# ...and you have a fully authenticated Canvas session! Pretty easy, right?
print(session.get('https://umich.instructure.com/').text)

# Now do whatever creepy things you want with Canvas!
```

### Development
Please post a issue or pull request if you see bugs or have any suggestions :)

### TODOs
* It'd be awesome to be able to also accept Duo requests automatically, but can introduce a security concern (anyone can just log into your account automatically, which breaks the purpose of 2fa already). Still, nice to have as a potential on/off feature. (Seems very hard and Duo disabled use of third party SSL certs, well done)
