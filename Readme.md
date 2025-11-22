#To update CVAT version(Current: 2.49.1 - alpha), run the following atleast once in a month

#Also Integrate with stable releases

  cd /Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/cvat
  docker-compose pull
  docker-compose up -d


#Create a environment and install the requirements 

#For installing the dependencies

pip install -r requirements.txt

#For Instantiating the Docker for Initial Setup

docker-compose up -d

docker exec -it cvat_server /bin/bash

# From inside the container's shell, run the following command 
# and follow the prompts to set a username, email, and password
python3 manage.py createsuperuser

exit

http://localhost:8080

#Once the proposals are generated, We need to create the tasks in Streamlit, Run

#bash "streamlit run /Users/surya/AVA_Kinetics/AVA_Kinetics_QC/processing_pipeline/jobs_UI.py"

In the Streamlit UI, Add the CVAT Admin User Name, Password, Path of Output Folder for Proposals need to be modified before task generation

#Webhook Listener needs to be Opened

python /Users/surya/AVA_Kinetics/AVA_Kinetics_QC/processing_pipeline/webhook_listener.py

#Afterwards, We need to setup the webhook in the CVAT

In the CVAT Home Screen, Projects -> Click on Your Project Name -> Actions (Right Hand Top Side) -> Setup Webhooks ->Click on '+'

In the Target URL; 

http://host.docker.internal:5001/webhook

Once, You click on Submit button, You need to 'Ping' once to check whether webhook listener is working or not properly. 


#Create a Tool That will help us visualise the Action Classes and Labels tagged on the Image / Video

#Step by Step of Instructions for Local Deployment and Environment Setup need to be documented

