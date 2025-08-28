# 🤖 Educational Telegram Bot

A production-ready educational Telegram bot with PostgreSQL database, user management, content delivery, and analytics - optimized for Railway deployment.

## Features

- **Arabic Language Support**: Full Arabic interface and commands
- **Student Management**: Registration, progress tracking, and analytics
- **Quiz System**: Excel import, multiple question types, automatic grading
- **Content Management**: Weekly materials, file uploads, multimedia support
- **Real-time Analytics**: Student performance, engagement metrics, dashboard
- **Automated Tasks**: Cleanup, notifications, reports generation
- **Webhook Support**: Production-ready webhook configuration
- **Docker Deployment**: Easy containerized deployment

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL (included in Docker setup)
- Telegram Bot Token

### 1. Get Bot Token

1. Contact [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

### 2. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd telebot

# Copy environment configuration
cp .env.example .env
```

### 3. Configure Environment

Edit `.env` file:

```bash
# Required: Your bot token
BOT_TOKEN=your_bot_token_here

# Required: Admin Telegram user IDs (comma-separated)
ADMIN_IDS=123456789,987654321

# Required: Database password
DB_PASSWORD=your_secure_password

# Optional: Webhook URL (for production)
WEBHOOK_URL=https://your-domain.com
```

### 4. Deploy

```bash
# Make deploy script executable
chmod +x deploy.sh

# Deploy in development mode
./deploy.sh deploy

# OR deploy in production mode
./deploy.sh deploy production
```

### 5. Verify Deployment

```bash
# Check service status
./deploy.sh status

# View logs
./deploy.sh logs

# Test health endpoint
curl http://localhost:8000/health
```

## Project Structure

```
telebot/
├── main.py                 # Application entry point
├── config/
│   └── settings.py         # Configuration management
├── models/
│   └── database.py         # Database models and operations
├── handlers/
│   └── student_handler.py  # Telegram message handlers
├── services/
│   ├── content_service.py  # Content management
│   ├── quiz_service.py     # Quiz operations and Excel parsing
│   └── analytics_service.py # Analytics and reporting
├── utils/
│   └── scheduler.py        # Background task scheduler
├── logs/                   # Application logs
├── uploads/                # User uploaded files
├── content/                # Educational content
└── quiz_templates/         # Quiz Excel templates
```

## Usage Guide

### Student Features

1. **Registration**: `/start` command begins registration
2. **Weekly Materials**: Browse and download course materials
3. **Quizzes**: Take quizzes with immediate feedback
4. **Progress Tracking**: View scores, streaks, and achievements
5. **Settings**: Manage notifications and profile

### Admin Features

1. **Statistics**: `/stats` - View bot analytics
2. **Broadcast**: `/broadcast <message>` - Send to all users
3. **Admin Panel**: `/admin` - Access admin functions

### Content Management

#### Adding Materials

Materials can be added through the admin interface or directly via the database.

#### Creating Quizzes from Excel

1. Create Excel file with columns:
   - `Question` or `سؤال`: Question text
   - `Option A`, `Option B`, etc.: Multiple choice options
   - `Correct Answer` or `الإجابة الصحيحة`: Correct answer
   - `Explanation` or `تفسير`: Answer explanation
   - `Difficulty` or `صعوبة`: easy/medium/hard

2. Upload through admin interface

## API Endpoints

- `GET /health` - Health check
- `POST /webhook/{bot_token}` - Telegram webhook
- `GET /` - Root endpoint

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram bot token | Required |
| `ADMIN_IDS` | Admin user IDs | Required |
| `DATABASE_URL` | Database connection | Auto-generated |
| `USE_WEBHOOK` | Enable webhook mode | true |
| `WEBHOOK_URL` | Public webhook URL | None |
| `DEBUG` | Debug mode | false |

### Database Configuration

The bot uses PostgreSQL with the following default settings:
- Database: `telebot`
- User: `telebot_user`
- Port: `5432`

## Deployment Options

### Development

```bash
# Local development with hot-reload
./deploy.sh deploy

# View logs
docker-compose logs -f telebot
```

### Production

```bash
# Production deployment with SSL
./deploy.sh deploy production

# Enable HTTPS with reverse proxy
# Configure your domain to point to the server
```

## Management Commands

```bash
# View service status
./deploy.sh status

# Create database backup
./deploy.sh backup

# Update application
./deploy.sh update

# Stop services
./deploy.sh stop

# View live logs
./deploy.sh logs
```

## Monitoring and Analytics

### Dashboard Features

- Real-time student activity
- Quiz performance metrics
- Content engagement analytics
- System health monitoring

### Automated Reports

- Daily activity summaries
- Weekly performance reports
- Monthly analytics archives

## Troubleshooting

### Common Issues

1. **Bot not responding**
   ```bash
   ./deploy.sh logs
   # Check for connection errors
   ```

2. **Database connection failed**
   ```bash
   docker-compose exec postgres pg_isready
   # Verify database is running
   ```

3. **Webhook not working**
   - Verify `WEBHOOK_URL` is accessible
   - Check SSL certificate validity
   - Ensure port 8000 is open

### Debug Mode

Enable debug logging:

```bash
# In .env file
DEBUG=true
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart telebot
```

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\\Scripts\\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export BOT_TOKEN=your_token
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost/telebot

# Run bot
python main.py
```

### Adding Features

1. **New Handlers**: Add to `handlers/` directory
2. **Services**: Extend services in `services/` directory
3. **Database**: Modify `models/database.py`
4. **Scheduled Tasks**: Add to `utils/scheduler.py`

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## Security Considerations

- Keep bot token secure
- Use strong database passwords
- Enable HTTPS in production
- Regularly backup data
- Monitor for suspicious activity

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check logs: `./deploy.sh logs`
2. Review configuration
3. Create GitHub issue with details

---

## Bot Commands Reference

### User Commands
- `/start` - Register and start using the bot
- `/help` - Show help information

### Admin Commands
- `/admin` - Access admin panel
- `/stats` - View bot statistics
- `/broadcast <message>` - Send message to all users

### Button Navigation
- 📚 المواد الأسبوعية - Weekly materials
- 📝 الاختبارات - Quizzes
- 📊 تقدمي - My progress
- ⚙️ الإعدادات - Settings
- 📞 التواصل - Contact support
- ℹ️ المساعدة - Help