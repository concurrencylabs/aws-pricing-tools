

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


**Rules:**
* The function only considers for price calculation those resources that are tagged. For example, if there is an untagged ELB
with tagged EC2 instances, the function will only consider the EC2 instances for the calculation.
If there is a tagged ELB with untagged EC2 instances, the function will only calculate price
for the ELB. 
* The behavior described above is intended for simplicity, otherwise the function would have to
cover a number of combinations that might or might not be suitable to all users of the function. 
* To keep it simple, if you want a resource to be included in the calculation, then tag it. Otherwise
leave it untagged.



## Install - using CloudFormation (recommended)


I created a CloudFormation template that deploys the Lambda function, as well as the CloudWatch Events
schedule. All you have to do is specify the tag key and value you want to calculate pricing for.
For example: TagKey:stack, TagValue:mywebapp

Click here to get started:

<a href="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=near-realtime-pricing-calculator&templateURL=http://s3.amazonaws.com/concurrencylabs-cfn-templates/lambda-near-realtime-pricing/function-plus-schedule.json" target="new"><img src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png" alt="Launch Stack"></a> 


### Updating to the latest version using CloudFormation

This function will be updated regularly in order to fix bugs and also to add more functionality.
This means you will likely have to update the function at some point. I recommend installing
the function using the CloudFormation template, since it will simplify the update process.

To update the function, just go to the CloudFormation console, select the stack you've created
and click on Actions -> Update Stack:

![Update CF stack](https://www.concurrencylabs.com/img/posts/11-ec2-pricing-lambda/update-stack.png)


Then select "Specify an Amazon S3 template URL" and enter the following value:


```
http://concurrencylabs-cfn-templates.s3.amazonaws.com/lambda-near-realtime-pricing/function-plus-schedule.json
```

![Select template](https://www.concurrencylabs.com/img/posts/11-ec2-pricing-lambda/update-function-select-template.png)

And that's it. CloudFormation will update the function with the latest code.



## Install - Manual steps



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

