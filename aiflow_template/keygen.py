# set AIRFLOW__CORE__FERNET_KEY="yLFfO_om4rzXsN6ikafusnOcpU2G_b7kJ5cixEfeuk4="

from cryptography.fernet import Fernet  

fernet_key = Fernet.generate_key() 
print(fernet_key.decode())