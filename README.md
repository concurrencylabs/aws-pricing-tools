

## Concurrency Labs - AWS Price Calculator tool

This repository uses the AWS Price List API to implement price calculation utilities.


Visit this URL for more details:

https://www.concurrencylabs.com/blog/aws-pricing-lambda-realtime-calculation-function/


The code is structured in the following way:

**pricecalculator**. The modules in this package interact directly with the AWS Price List API.
They take price dimension parameters as inputs and return results in JSON format. This package
is called by Lambda functions or other Python scripts.

**functions**. This is where our Lambda functions live. Functions are created using the Serverless framework.

Available functions:

* calculate-near-realtime. This function is called by a schedule configured using CloudWatch Events. 
The function receives a JSON object configured in the schedule. The JSON object has the format ```{"tag":{"key":"mykey","value":"myvalue"}}```.
The function finds EC2 resources with the corresponding tag, gets current usage using CloudWatch metrics,
projects usage into a longer time period (i.e. a month), calls pricecalculator to calculate price 
and puts results in CloudWatch metrics.


## Set up


### Create an isolated Python environment using virtualenv

It's always a good practice to create an isolated environment so we have greater control over
the dependencies in our project, including the Python runtime.

If you don't have virtualenv installed, run:

```
pip install virtualenv
```

For more details on virtualenv, <a href="https://virtualenv.pypa.io/en/stable/installation/" target="new">click here.</a>

Now, create a Python 2.7 virtual environment where your project will live. If you want to name your project
aws-pricing, then run:

```
virtualenv aws-pricing -p python2.7
```

After your environment is created, it's time to activate it. Go to the recently created
folder of your project (i.e. aws-pricing) and from there run:

```
source bin/activate
```

### Install python-local-lambda

The Serverless framework is a great way to create, configure and deploy projects based on AWS Lambda - 
as well as other services, such as API Gateway. But you still need to test your
functions locally before deploying. For a Lambda function using the Python 2.7 runtime, I use <a href="https://pypi.python.org/pypi/python-lambda-local/0.1.2" target="new">python-local-lambda</a>

**python-local-lambda** lets me test my Lambda functions locally using test events in my workstation.


From your project root folder, run:

```
pip install python-lambda-local
```


### Install Boto 3

If you're going to run the Lambda function locally, you need to have the AWS SDK installed, since
the function calls EC2 and CloudWatch APIs. This is why we need Boto 3.

```
pip install boto3
```


### Install the Serverless Framework

![ServerlessLogo](https://www.concurrencylabs.com/img/posts/11-ec2-pricing-lambda/serverless_logo.png)


Since the pricing tool runs on AWS Lambda, I decided to use the <a href="http://serverless.com/" target="new">Serverless Framework</a>. 
This framework enormously simplifies the development, configuration and deployment of Function as a Service (a.k.a. FaaS, or "serverless")
code into AWS Lambda.


You should follow the instructions described <a href="https://github.com/serverless/serverless/blob/master/docs/guide/installation.md" target="new">here</a>,
which can be summarized in the following steps:

1. Make sure you have Node.js <a href="https://nodejs.org/en/download/" target="new">installed</a> in your workstation.
```
node --version
```

2. Install the Serverless Framework
```
npm install -g serverless@beta
```


3. Confirm Serverless has been installed
```
serverless --version
```
The steps in this post were tested using version ```1.0.0-beta.2```


4. Serverless needs access to your AWS account, so it can create and update AWS Lambda 
functions, among other operations. Therefore, you have to make sure Serverless can access 
a set of IAM  User credentials. Follow <a href="https://github.com/serverless/serverless/blob/master/docs/guide/provider-account-setup.md" target="new">these instructions</a>.
In the long term, you should make sure these credentials are limited to only the API operations
Serverless requires - avoid Administrator access, which is a bad security and operational practice.


5. Checkout the code from this repo into your virtualenv folder.


### Testing the function locally


Once you have: virtualenv activated, Boto3, Serverless and python-local-lambda installed as well
as the code checked out, it's time to run a test.

Update ```test-events/constant-tag.json``` with a tag key/value pair that exists in your AWS account.
Then run:

```
python-lambda-local functions/calculate-near-realtime.py test-events/constant-tag.json -l lib/ -l . -f handler -t 30 -a arn:aws:lambda:us-east-1:123456789012:function:realtime-pricing-ec2-calculate
```


### Updating the AWS Price List API Index file

The code in this repo uses a local copy of the the AWS Price List API index file. This index file
is constantly updated by AWS. Since price accuracy depends on having the latest file, we
have to make sure we run our code using the latest index file. I recommend subscribing to the AWS Price List API
change notifications. In order to download the latest index file, go to the "scripts" folder
and run:

```
python get-latest-index.py --service=ec2
```

Make sure your virtualenv is activated, or that you are running the script using Python 2.7

