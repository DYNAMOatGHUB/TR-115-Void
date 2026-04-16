#!/bin/bash

# startup.sh — Start producer and consumer services automatically
# Usage: ./startup.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/.venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
    echo "Please run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Load environment variables from .env
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(cat "$PROJECT_DIR/.env" | grep -v '^#' | xargs)
    echo -e "${GREEN}✓ Loaded .env variables${NC}"
else
    echo -e "${YELLOW}⚠ No .env file found${NC}"
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Function to check if a process is running
is_running() {
    local service=$1
    pgrep -f "python.*$service.py" > /dev/null 2>&1
    return $?
}

# Function to start a service
start_service() {
    local service=$1
    local log_file="$PROJECT_DIR/logs/${service}.log"
    
    if is_running "$service"; then
        echo -e "${YELLOW}⚠ $service is already running${NC}"
        return
    fi
    
    echo -e "${YELLOW}Starting $service...${NC}"
    cd "$PROJECT_DIR"
    source "$VENV_PATH/bin/activate"
    
    nohup python "$service.py" > "$log_file" 2>&1 &
    local pid=$!
    
    sleep 2
    
    if is_running "$service"; then
        echo -e "${GREEN}✓ $service started (PID: $pid)${NC}"
        echo "   Logs: $log_file"
    else
        echo -e "${RED}❌ Failed to start $service${NC}"
        echo "   Check logs: $log_file"
        return 1
    fi
}

# Function to stop a service
stop_service() {
    local service=$1
    
    if is_running "$service"; then
        echo -e "${YELLOW}Stopping $service...${NC}"
        pkill -f "python.*$service.py"
        sleep 1
        echo -e "${GREEN}✓ $service stopped${NC}"
    else
        echo -e "${YELLOW}⚠ $service is not running${NC}"
    fi
}

# Function to show status
show_status() {
    echo -e "\n${YELLOW}Service Status:${NC}"
    
    if is_running "producer"; then
        local pid=$(pgrep -f "python.*producer.py" | head -1)
        echo -e "  ${GREEN}✓ Producer${NC} (PID: $pid)"
    else
        echo -e "  ${RED}✗ Producer${NC}"
    fi
    
    if is_running "consumer"; then
        local pid=$(pgrep -f "python.*consumer.py" | head -1)
        echo -e "  ${GREEN}✓ Consumer${NC} (PID: $pid)"
    else
        echo -e "  ${RED}✗ Consumer${NC}"
    fi
    
    echo ""
}

# Main logic
case "${1:-start}" in
    start)
        echo -e "${GREEN}🚀 Starting Carbon Intelligence Services${NC}\n"
        start_service "producer"
        start_service "consumer"
        show_status
        echo -e "${GREEN}All services started!${NC}"
        echo -e "View logs: tail -f logs/producer.log logs/consumer.log"
        ;;
    stop)
        echo -e "${YELLOW}⛔ Stopping Carbon Intelligence Services${NC}\n"
        stop_service "producer"
        stop_service "consumer"
        show_status
        ;;
    restart)
        echo -e "${YELLOW}🔄 Restarting Carbon Intelligence Services${NC}\n"
        stop_service "producer"
        stop_service "consumer"
        sleep 2
        start_service "producer"
        start_service "consumer"
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        echo -e "${YELLOW}📋 Service Logs:${NC}\n"
        if [ -f "logs/producer.log" ] || [ -f "logs/consumer.log" ]; then
            tail -f logs/producer.log logs/consumer.log 2>/dev/null || echo "No logs found yet"
        else
            echo "No logs found. Start services first: ./startup.sh start"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start      — Start producer and consumer services"
        echo "  stop       — Stop all services"
        echo "  restart    — Restart all services"
        echo "  status     — Show service status"
        echo "  logs       — Stream service logs"
        exit 1
        ;;
esac
