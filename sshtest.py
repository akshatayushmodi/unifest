import psycopg2
import paramiko
import getpass

# SSH Credentials
ssh_params = {
    'hostname': '10.5.18.70',
    'username': '21CS30035',
    'password': 'xxx',  # or provide key_filename for key-based authentication
}

# Database connection parameters for PostgreSQL
db_params_postgresql = {
    'dbname': '21CS30035',
    'user': '21CS30035',
    'password': '21CS30035',
    'host': '10.5.18.70',
    'port': '5432',
}


def connect_to_postgresql():
    # Create an SSH tunnel
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(**ssh_params, allow_agent=False, look_for_keys=False)

    # Set up the tunnel
    ssh_transport = ssh_client.get_transport()
    local_port = 5432  # local port to forward to PostgreSQL server
    dest_addr = (db_params_postgresql['host'], int(db_params_postgresql['port']))
    local_addr = ('localhost', local_port)
    ssh_channel = ssh_transport.open_channel('direct-tcpip', dest_addr, local_addr)

    # Connect to PostgreSQL through the tunnel
    connection = psycopg2.connect(
        database=db_params_postgresql['dbname'],
        user=db_params_postgresql['user'],
        password=db_params_postgresql['password'],
        host='10.5.18.70',
        port=local_port,
    )

    print("Connected to PostgreSQL database via SSH tunnel.")
    return connection


if __name__ == "__main__":
    ssh_params['password'] = getpass.getpass("Please enter ssh password: ")
    connection = connect_to_postgresql()
    if connection is None:
        exit(0)

    try:
    #enter main code
        pass
    finally:
        connection.close()
        print("Connection closed.")

