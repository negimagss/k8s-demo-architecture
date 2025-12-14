#!/bin/bash
echo "Deleting Local Key Cluster..."
kind delete cluster --name local-test-cluster
echo "Done."
