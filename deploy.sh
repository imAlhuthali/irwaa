#!/bin/bash

# Educational Telegram Bot Deployment Script
# This script helps deploy the bot in different environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required commands exist
check_requirements() {
    log_info "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log_success "Requirements check passed"
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log_warning "Created .env file from .env.example. Please configure it before continuing."
            log_info "Edit .env file with your configuration:"
            log_info "- Set BOT_TOKEN to your Telegram bot token"
            log_info "- Set ADMIN_IDS to your Telegram user ID"
            log_info "- Configure database credentials"
            log_info "- Set WEBHOOK_URL if using webhooks"
            read -p "Press Enter after configuring .env file..."
        else
            log_error ".env.example file not found. Please create .env file manually."
            exit 1
        fi
    fi
    
    log_success "Environment setup completed"
}

# Validate environment configuration
validate_config() {
    log_info "Validating configuration..."
    
    # Check if required env vars are set
    source .env
    
    if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
        log_error "BOT_TOKEN is not configured in .env file"
        exit 1
    fi
    
    if [ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "your_secure_password" ]; then
        log_error "DB_PASSWORD is not configured in .env file"
        exit 1
    fi
    
    log_success "Configuration validation passed"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p uploads
    mkdir -p content
    mkdir -p quiz_templates
    mkdir -p backups
    
    # Set permissions
    chmod 755 logs uploads content quiz_templates backups
    
    log_success "Directories created"
}

# Build and start services
deploy_services() {
    local environment=$1
    
    log_info "Building and starting services for $environment environment..."
    
    if [ "$environment" = "production" ]; then
        # Production deployment with nginx
        docker-compose --profile production up -d --build
    else
        # Development deployment
        docker-compose up -d --build
    fi
    
    # Wait for services to be healthy
    log_info "Waiting for services to start..."
    sleep 30
    
    # Check service health
    if docker-compose ps | grep -q "Up (healthy)"; then
        log_success "Services started successfully"
    else
        log_error "Some services failed to start. Check logs with: docker-compose logs"
        exit 1
    fi
}

# Initialize database
init_database() {
    log_info "Initializing database..."
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U ${DB_USER:-telebot_user} -d ${DB_NAME:-telebot}; then
            break
        fi
        sleep 2
    done
    
    # Run database migrations (if you add Alembic later)
    # docker-compose exec telebot python -m alembic upgrade head
    
    log_success "Database initialized"
}

# Setup SSL certificates (for production)
setup_ssl() {
    if [ ! -d "ssl" ]; then
        log_info "Setting up SSL certificates..."
        mkdir -p ssl
        
        # Generate self-signed certificate (for testing)
        # In production, replace with real certificates
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ssl/private.key \
            -out ssl/certificate.crt \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        
        log_warning "Generated self-signed SSL certificate. Replace with real certificate in production."
    fi
}

# Backup database
backup_database() {
    log_info "Creating database backup..."
    
    backup_file="backups/telebot_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    docker-compose exec -T postgres pg_dump -U ${DB_USER:-telebot_user} ${DB_NAME:-telebot} > "$backup_file"
    
    log_success "Database backup created: $backup_file"
}

# Show status
show_status() {
    log_info "Service Status:"
    docker-compose ps
    
    echo ""
    log_info "Application Logs (last 20 lines):"
    docker-compose logs --tail=20 telebot
    
    echo ""
    log_info "Health Check:"
    if curl -f http://localhost:8000/health 2>/dev/null; then
        log_success "Application is healthy"
    else
        log_warning "Application health check failed"
    fi
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    docker-compose down
    log_success "Services stopped"
}

# Update application
update_app() {
    log_info "Updating application..."
    
    # Pull latest changes (if using git)
    if [ -d ".git" ]; then
        git pull
    fi
    
    # Backup before update
    backup_database
    
    # Rebuild and restart
    docker-compose down
    docker-compose up -d --build
    
    log_success "Application updated"
}

# Main function
main() {
    case ${1:-deploy} in
        "deploy")
            environment=${2:-development}
            log_info "Starting deployment for $environment environment..."
            
            check_requirements
            setup_environment
            validate_config
            create_directories
            
            if [ "$environment" = "production" ]; then
                setup_ssl
            fi
            
            deploy_services $environment
            init_database
            
            log_success "Deployment completed successfully!"
            log_info "Bot is running on port 8000"
            log_info "Use 'docker-compose logs -f telebot' to view live logs"
            ;;
        "status")
            show_status
            ;;
        "stop")
            stop_services
            ;;
        "backup")
            backup_database
            ;;
        "update")
            update_app
            ;;
        "logs")
            docker-compose logs -f telebot
            ;;
        *)
            echo "Usage: $0 {deploy|status|stop|backup|update|logs} [environment]"
            echo ""
            echo "Commands:"
            echo "  deploy [dev|production]  - Deploy the bot (default: development)"
            echo "  status                   - Show service status"
            echo "  stop                     - Stop all services"
            echo "  backup                   - Create database backup"
            echo "  update                   - Update and restart the application"
            echo "  logs                     - View live logs"
            echo ""
            echo "Examples:"
            echo "  $0 deploy                - Deploy in development mode"
            echo "  $0 deploy production     - Deploy in production mode"
            echo "  $0 status               - Check service status"
            echo "  $0 logs                 - View live logs"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"