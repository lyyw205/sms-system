#!/bin/bash
# Setup script for SMS System Integration

echo "🚀 SMS System Integration Setup"
echo "================================"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check database connection
echo ""
echo "🔍 Checking database connection..."
python3 -c "
from app.db.database import engine
try:
    with engine.connect() as conn:
        print('✓ Database connection successful')
except Exception as e:
    print(f'✗ Database connection failed: {e}')
    exit(1)
"

# Run migrations
echo ""
echo "🔄 Running database migrations..."
alembic upgrade head

# Create default templates
echo ""
echo "📝 Creating default message templates..."
python3 -c "
from app.db.database import SessionLocal
from app.db.models import MessageTemplate
import json

db = SessionLocal()

# Room guide template
room_template = MessageTemplate(
    key='room_guide',
    name='Room Guide Message',
    content='''금일 객실은 스테이블 {{building}}동 {{roomNumber}}호 - {{roomInfo}}룸입니다.(비밀번호: {{roomPassword}}*)

무인 체크인이라서 바로 입실하시면 됩니다.
객실내에서(발코니포함) 음주, 흡연, 취식, 혼숙 절대 금지입니다.(적발시 벌금 10만원 또는 퇴실)

파티 참여 시 저녁 8시에 B동 1층 포차로 내려와 주시면 되세요.

차량번호 회신 반드시 해주시고, 주차는 아래 자주묻는질문 링크를 참고하여 타차량 통행 가능하도록 해주세요.
자주묻는질문: https://bit.ly/3Ej6P9A''',
    variables=json.dumps(['building', 'roomNumber', 'roomInfo', 'roomPassword']),
    category='room_guide',
    active=True
)

try:
    existing = db.query(MessageTemplate).filter_by(key='room_guide').first()
    if not existing:
        db.add(room_template)
        db.commit()
        print('✓ Created room_guide template')
    else:
        print('✓ room_guide template already exists')
except Exception as e:
    print(f'✗ Error creating template: {e}')
    db.rollback()
finally:
    db.close()
"

# Summary
echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure environment variables in .env:"
echo "   - DEMO_MODE=false (for production)"
echo "   - NAVER_RESERVATION_EMAIL"
echo "   - NAVER_RESERVATION_PASSWORD"
echo "   - GOOGLE_SHEETS_CREDENTIALS"
echo ""
echo "2. Start the server:"
echo "   uvicorn app.main:app --reload"
echo ""
echo "3. Access the API documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "4. Check scheduler status:"
echo "   curl http://localhost:8000/scheduler/jobs"
