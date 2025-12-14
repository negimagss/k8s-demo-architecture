#!/bin/bash
set -e

echo "1. Regenerating ConfigMap from code/..."
kubectl create configmap backend-script \
    --from-file=app.py=code/app.py \
    --from-file=worker.py=code/worker.py \
    --from-file=index.html=code/html/index.html \
    --from-file=space.html=code/html/space.html \
    --from-file=webgl.html=code/html/webgl.html \
    --from-file=architecture.html=code/html/architecture.html \
    --from-file=landing.html=code/html/landing.html \
    --from-file=health_check.py=code/health_check.py \
    -n local-test \
    --dry-run=client -o yaml > deployment/04-backend-configmap.yaml

echo "2. Applying new ConfigMap..."
kubectl apply -f deployment/04-backend-configmap.yaml

echo "3. Restarting Backend & Worker Pods to pick up changes..."
kubectl rollout restart deployment debug-scakable -n local-test
kubectl rollout restart deployment worker -n local-test

echo "4. Waiting for rollout..."
kubectl rollout status deployment debug-scakable -n local-test

echo "------------------------------------------------"
echo "✅ Update Complete!"
echo "Test url: http://localhost:80/save?data=NewDesign"
