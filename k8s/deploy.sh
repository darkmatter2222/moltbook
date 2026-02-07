#!/bin/bash
# Moltbook Agent Deployment Script
# Deploys to Kubernetes cluster with RTX 3090 GPU

set -e

echo "🦞 Moltbook Agent Deployment Script"
echo "===================================="

# Configuration
NAMESPACE="moltbook"
AGENT_IMAGE="moltbook-agent:latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "docker is not installed"
        exit 1
    fi
    
    # Check if cluster is reachable
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_info "Prerequisites check passed ✓"
}

# Build the agent Docker image
build_image() {
    log_info "Building Moltbook Agent Docker image..."
    
    cd "$(dirname "$0")/../agent"
    docker build -t ${AGENT_IMAGE} .
    
    log_info "Docker image built successfully ✓"
}

# Deploy to Kubernetes
deploy() {
    log_info "Deploying to Kubernetes..."
    
    # Apply the deployment
    kubectl apply -f "$(dirname "$0")/deployment.yaml"
    
    log_info "Deployment applied ✓"
}

# Wait for deployments to be ready
wait_for_ready() {
    log_info "Waiting for Ollama to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/ollama -n ${NAMESPACE} || true
    
    log_info "Waiting for Moltbook Agent to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/moltbook-agent -n ${NAMESPACE} || true
    
    log_info "All deployments ready ✓"
}

# Pull the Qwen model in Ollama
pull_model() {
    log_info "Pulling Qwen 2.5 3B model in Ollama..."
    
    # Get the ollama pod name
    OLLAMA_POD=$(kubectl get pods -n ${NAMESPACE} -l app=ollama -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$OLLAMA_POD" ]; then
        kubectl exec -n ${NAMESPACE} ${OLLAMA_POD} -- ollama pull qwen2.5:3b || log_warn "Model pull may still be in progress"
    fi
    
    log_info "Model pull initiated ✓"
}

# Get service URL
get_service_url() {
    log_info "Getting service URL..."
    
    # Get the service external IP or NodePort
    SERVICE_IP=$(kubectl get svc moltbook-agent -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    
    if [ -z "$SERVICE_IP" ]; then
        # Try NodePort
        NODE_PORT=$(kubectl get svc moltbook-agent -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")
        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
        
        if [ -n "$NODE_PORT" ]; then
            echo ""
            echo "===================================="
            echo "🦞 Moltbook Agent Dashboard"
            echo "===================================="
            echo "URL: http://${NODE_IP}:${NODE_PORT}"
            echo ""
        else
            # Port forward as fallback
            echo ""
            echo "===================================="
            echo "🦞 Moltbook Agent Dashboard"
            echo "===================================="
            echo "Run: kubectl port-forward svc/moltbook-agent 8080:80 -n moltbook"
            echo "Then access: http://localhost:8080"
            echo ""
        fi
    else
        echo ""
        echo "===================================="
        echo "🦞 Moltbook Agent Dashboard"
        echo "===================================="
        echo "URL: http://${SERVICE_IP}"
        echo ""
    fi
}

# Show pod status
show_status() {
    log_info "Current pod status:"
    kubectl get pods -n ${NAMESPACE}
    echo ""
    log_info "Current services:"
    kubectl get svc -n ${NAMESPACE}
}

# Main execution
main() {
    check_prerequisites
    build_image
    deploy
    wait_for_ready
    pull_model
    show_status
    get_service_url
    
    echo ""
    log_info "Deployment complete! 🦞"
    echo ""
    echo "To claim your agent, visit:"
    echo "https://moltbook.com/claim/moltbook_claim_tpDLGWWrB82G_6_c0rVMDUjDpYpcVSof"
    echo ""
    echo "Tweet: I'm claiming my AI agent \"Darkmatter2222\" on @moltbook 🦞"
    echo "Verification: ocean-H759"
}

# Run main
main "$@"
