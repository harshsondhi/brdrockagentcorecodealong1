import boto3
import json

client = boto3.client('bedrock-agentcore', region_name='us-west-2')
payload = json.dumps({"prompt": "Data, tell me who created you"})

response = client.invoke_agent_runtime(
    agentRuntimeArn='arn:aws:bedrock-agentcore:us-west-2:615345689',
    runtimeSessionId='m7Qp9Xv2Lk8Rz4Nw1Tj6Hs3Bd0Fy5Ua7EcP', # Must be 33+ char. Every new SessionId will create a new MicroVM
    payload=payload,
    qualifier="DEFAULT" # This is Optional. When the field is not provided, Runtime will use DEFAULT endpoint
)
response_body = response['response'].read()
response_data = json.loads(response_body)
print("Agent Response:", response_data)
