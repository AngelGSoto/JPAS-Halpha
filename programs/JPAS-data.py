#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pyvo.dal
from pyvo.auth import authsession, securitymethods
import getpass
import requests
import pyvo


# In[2]:


# To avoid warnings
import warnings
warnings.simplefilter("ignore")


# In[3]:


# Url of the TAP service
tap_url = "https://archive.cefca.es/catalogues/vo/tap/jpas-idr202406"


# In[9]:


# Login
user = input("Username:")
pwd = getpass.getpass("Password:")
archive_login_url = "https://archive.cefca.es/catalogues/login"
login_args = {"login": user, "password": pwd,
              "submit": "Sign+In"}
login_header = {"Content-type": "application/x-www-form-urlencoded",
                "Accept": "text/plain"}


# In[10]:


pyvo.dal.tap.s = requests.Session()
response = pyvo.dal.tap.s.post(archive_login_url,
                 data=login_args, headers=login_header)


# In[11]:


response.raise_for_status()


# In[12]:


auth = authsession.AuthSession()
auth.credentials.set(securitymethods.ANONYMOUS, pyvo.dal.tap.s)


# In[13]:


# Ejecutando la consulta
service = pyvo.dal.TAPService(tap_url, session=auth)
resultset = service.run_sync("SELECT COUNT(*) as total FROM jpas.DuplicatedMagABDualObj WHERE MAG_ERR_APER_6_0[jpas::J0660] < 0.2 AND MAG_ERR_APER_6_0[jpas::iSDSS] < 0.2")


# In[14]:


# Convertir a tabla Astropy
table = resultset.to_table()


# In[15]:


# Obtener el número total de objetos
total_objects = table[0]["total"]
print("El total de objetos en el survey es:", total_objects)


# #### Probemos async

# In[16]:


job = service.run_async("SELECT TOP 100 * FROM jpas.DuplicatedMagABDualObj WHERE MAG_ERR_APER_6_0[jpas::J0660] < 0.2 AND MAG_ERR_APER_6_0[jpas::iSDSS] < 0.2")


# In[21]:


# Convertir a tabla de Astropy
table = job.to_table()
type(table)


# In[22]:


# Mostrar los primeros registros
print(table)


# In[24]:


for i in table.columns:
    print(i)


# # Verlos filtros

# In[22]:


resultset = service.run_sync("SELECT * FROM  jpas.Filter")  
print(resultset.to_table())


# In[23]:


filters = resultset.to_table()


# In[30]:


f660 = filters["name"]== "J0660"
filter_f660 = filters[f660]
filter_f660


# In[ ]:




