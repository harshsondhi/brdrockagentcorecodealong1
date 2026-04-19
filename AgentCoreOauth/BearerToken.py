import boto3
import getpass

def get_bearer_token():
    region = 'us-west-2'  # Update this to your desired region
    
    client_id = input("Enter the Cognito App Client ID: ")
    user_name = input("Enter the Cognito username: ")
    password = getpass.getpass("Enter the Cognito user password: ")
    
    cognito = boto3.client('cognito-idp', region_name=region)
    
    client = boto3.client('cognito-idp', region_name=region)

    try:
        response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )

        token = response['AuthenticationResult']['AccessToken']
        print("\n✅ Authentication successful.")
        print(f"Bearer Token (AccessToken):\n{token}")

    except client.exceptions.NotAuthorizedException:
        print("❌ Authentication failed: Invalid username or password.")
    except client.exceptions.UserNotConfirmedException:
        print("❌ Authentication failed: User is not confirmed.")
    except client.exceptions.UserNotFoundException:
        print("❌ Authentication failed: User not found.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        
        
if __name__ == "__main__":
    get_bearer_token()        