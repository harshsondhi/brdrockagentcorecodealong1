import boto3
import getpass

user_pool_name = input("Enter the name of the Cognito User Pool you want to use: ")
client_name = input("Enter the name of the Cognito App Client you want to use: ")
user_name = input("Enter the username for the Cognito user you want to create: ")
permanent_password = getpass.getpass("Enter the password for the Cognito user you want to create: ")

region = 'us-west-2'  # Update this to your desired region
temporary_password = 'TempPass123@#!'  # Temporary password for the new user

cognito = boto3.client('cognito-idp', region_name=region)

#### create user pool
print(f"Creating Cognito User Pool '{user_pool_name}'...")
user_pool_response = cognito.create_user_pool(
    PoolName=user_pool_name,
    Policies={
        'PasswordPolicy': {
            'MinimumLength': 8,
        }
    }
)
user_pool_id = user_pool_response['UserPool']['Id']
print(f"User Pool created with ID: {user_pool_id}")   


#### create app client
print(f"Creating App Client '{client_name}' in User Pool '{user_pool_name}'...")
client_response = cognito.create_user_pool_client(
    UserPoolId=user_pool_id,
    ClientName=client_name,
    GenerateSecret=False,
    ExplicitAuthFlows=['ALLOW_USER_PASSWORD_AUTH', 'ALLOW_REFRESH_TOKEN_AUTH']
)
print(f"App Client created with ID: {client_response['UserPoolClient']['ClientId']}")
client_id = client_response['UserPoolClient']['ClientId']

print(f"Creating user '{user_name}' in User Pool '{user_pool_name}'...")
cognito.admin_create_user(
    UserPoolId=user_pool_id,
    Username=user_name,
    TemporaryPassword=temporary_password,
    MessageAction='SUPPRESS'  # Suppress sending the welcome email
)

print(f"Setting permanent password for user '{user_name}'...")
cognito.admin_set_user_password(
    UserPoolId=user_pool_id,
    Username=user_name,
    Password=permanent_password,
    Permanent=True
)

print("Cognito setup complete! get auth token using the following details:")

auth_response = cognito.initiate_auth(  
    ClientId=client_id,
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={
        'USERNAME': user_name,
        'PASSWORD': permanent_password
    }
)
print(f"Auth token: {auth_response['AuthenticationResult']['AccessToken']}")
access_token = auth_response['AuthenticationResult']['AccessToken']

print("\n✅ Setup Complete")
print(f"Pool ID: {pool_id}")
print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
print(f"Client ID: {client_id}")
print(f"Bearer Token: {access_token}")