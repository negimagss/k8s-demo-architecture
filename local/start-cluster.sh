#!/bin/bash
set -e

CLUSTER_NAME="local-test-cluster"

echo "Checking for existing cluster '$CLUSTER_NAME'..."
if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
    echo "Cluster '$CLUSTER_NAME' already exists."
else
    echo "Creating cluster '$CLUSTER_NAME'..."
    kind create cluster --name "$CLUSTER_NAME" --config deployment/kind-config.yaml
fi

echo "Switching context to 'kind-$CLUSTER_NAME'..."
kubectl config use-context "kind-$CLUSTER_NAME"


# Generate backend configmap from external code
kubectl create configmap backend-script \
    --from-file=app.py=code/app.py \
    --from-file=worker.py=code/worker.py \
    --from-file=index.html=code/index.html \
    --from-file=space.html=code/html/space.html \
    --from-file=webgl.html=code/html/webgl.html \
    --from-file=architecture.html=code/html/architecture.html \
    -n local-test \
    --dry-run=client -o yaml > deployment/04-backend-configmap.yaml

echo "Applying manifests..."
kubectl apply -f "deployment/00-namespace.yaml" \
    -f "deployment/07-owner-secret.yaml" \
    -f "deployment/10-db-secret.yaml" \
    -f "deployment/04-backend-configmap.yaml" \
    -f "deployment/05-backend-service.yaml" \
    -f "deployment/08-rabbitmq.yaml" \
    -f "deployment/09-postgres.yaml" \
    -f "deployment/03-debug-pod.yaml" \
    -f "deployment/11-worker-deployment.yaml" \
    -f "deployment/06-nginx-configmap.yaml" \
    -f "deployment/01-deployment.yaml" \
    -f "deployment/02-service.yaml"

echo "Waiting for pods to be created..."
sleep 5

echo "Waiting for Nginx deployment roll out..."
kubectl rollout status deployment/nginx-local -n local-test --timeout=90s

echo "Setup complete!"
echo "You can access Nginx at http://localhost:80"
echo "To debug, run: kubectl exec -it -n local-test debug-pod -- sh"
