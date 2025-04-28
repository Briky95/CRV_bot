#!/bin/bash

# Script per verificare lo stato del bot Telegram e dell'interfaccia web su AWS

# Verifica che AWS CLI sia installato
if ! command -v aws &> /dev/null; then
    echo "AWS CLI non è installato. Installalo con 'pip install awscli' e configura le credenziali."
    exit 1
fi

# Verifica che le credenziali AWS siano configurate
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Le credenziali AWS non sono configurate. Esegui 'aws configure' per configurarle."
    exit 1
fi

# Nome dello stack CloudFormation
STACK_NAME="RugbyBotStack"

# Ottieni il token del bot da .env
BOT_TOKEN=$(grep BOT_TOKEN .env | cut -d '=' -f2)

# Verifica lo stato dello stack CloudFormation
echo "Verifica dello stato dello stack CloudFormation..."
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].StackStatus" --output text 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "Lo stack $STACK_NAME non esiste o non è accessibile."
    exit 1
fi

echo "Stato dello stack: $STACK_STATUS"

# Ottieni gli output dello stack
echo "Ottenimento degli output dello stack..."
BOT_WEBHOOK_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='BotWebhookUrl'].OutputValue" --output text)
WEB_INTERFACE_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='WebInterfaceUrl'].OutputValue" --output text)

echo "URL del webhook del bot: $BOT_WEBHOOK_URL"
echo "URL dell'interfaccia web: $WEB_INTERFACE_URL"

# Verifica lo stato del webhook del bot
echo "Verifica dello stato del webhook del bot..."
WEBHOOK_INFO=$(curl -s -X POST https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo)
echo "Informazioni sul webhook: $WEBHOOK_INFO"

# Verifica lo stato delle funzioni Lambda
echo "Verifica dello stato delle funzioni Lambda..."
BOT_FUNCTION=$(aws cloudformation describe-stack-resources --stack-name $STACK_NAME --logical-resource-id BotLambdaFunction --query "StackResources[0].PhysicalResourceId" --output text)
WEB_FUNCTION=$(aws cloudformation describe-stack-resources --stack-name $STACK_NAME --logical-resource-id WebLambdaFunction --query "StackResources[0].PhysicalResourceId" --output text)

echo "Funzione Lambda del bot: $BOT_FUNCTION"
echo "Funzione Lambda dell'interfaccia web: $WEB_FUNCTION"

# Verifica i log recenti delle funzioni Lambda
echo "Ultimi log della funzione Lambda del bot:"
aws logs get-log-events --log-group-name /aws/lambda/$BOT_FUNCTION --log-stream-name $(aws logs describe-log-streams --log-group-name /aws/lambda/$BOT_FUNCTION --order-by LastEventTime --descending --limit 1 --query "logStreams[0].logStreamName" --output text) --limit 10 --query "events[*].message" --output text

echo "Ultimi log della funzione Lambda dell'interfaccia web:"
aws logs get-log-events --log-group-name /aws/lambda/$WEB_FUNCTION --log-stream-name $(aws logs describe-log-streams --log-group-name /aws/lambda/$WEB_FUNCTION --order-by LastEventTime --descending --limit 1 --query "logStreams[0].logStreamName" --output text) --limit 10 --query "events[*].message" --output text

# Verifica la connettività dell'interfaccia web
echo "Verifica della connettività dell'interfaccia web..."
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $WEB_INTERFACE_URL)
echo "Stato HTTP dell'interfaccia web: $WEB_STATUS"

# Suggerimenti per la risoluzione dei problemi
echo ""
echo "Suggerimenti per la risoluzione dei problemi:"
echo "1. Se il webhook non è configurato correttamente, esegui:"
echo "   curl -X POST https://api.telegram.org/bot$BOT_TOKEN/setWebhook -d url=$BOT_WEBHOOK_URL"
echo ""
echo "2. Se le funzioni Lambda hanno errori, controlla i log completi con:"
echo "   aws logs get-log-events --log-group-name /aws/lambda/$BOT_FUNCTION --log-stream-name NOME_STREAM"
echo "   aws logs get-log-events --log-group-name /aws/lambda/$WEB_FUNCTION --log-stream-name NOME_STREAM"
echo ""
echo "3. Per aggiornare lo stack, esegui:"
echo "   ./deploy_to_aws.sh"
echo ""
echo "4. Per eliminare lo stack e ricrearlo, esegui:"
echo "   aws cloudformation delete-stack --stack-name $STACK_NAME"
echo "   ./deploy_to_aws.sh"