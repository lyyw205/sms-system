"""
Quick test script to verify Mock providers work without database
Run: python test_mock.py
"""
import asyncio
from app.config import settings
from app.factory import get_sms_provider, get_llm_provider, get_reservation_provider, get_storage_provider
from app.rules.engine import RuleEngine
from app.router.message_router import MessageRouter

print("=" * 60)
print("SMS 예약 시스템 - Mock Provider 테스트")
print("=" * 60)
print(f"DEMO_MODE: {settings.DEMO_MODE}")
print()

async def test_sms():
    print("1️⃣  SMS Provider 테스트")
    print("-" * 60)
    provider = get_sms_provider()

    # 발송 테스트
    result = await provider.send_sms(to="010-1234-5678", message="테스트 메시지")
    print(f"✅ SMS 발송 결과: {result['status']}")

    # 수신 시뮬레이션
    result = await provider.simulate_receive(
        from_="010-1234-5678",
        to="010-9999-0000",
        message="영업시간이 어떻게 되나요?"
    )
    print(f"✅ SMS 수신 시뮬레이션: {result['status']}")
    print()

async def test_rules():
    print("2️⃣  룰 엔진 테스트")
    print("-" * 60)
    engine = RuleEngine()

    test_messages = [
        "영업시간이 어떻게 되나요?",
        "가격이 얼마인가요?",
        "주차 가능한가요?",
        "할인 행사 있나요?",  # 룰 매칭 실패 예상
    ]

    for msg in test_messages:
        result = engine.match(msg)
        if result:
            print(f"✅ '{msg}' → 매칭 성공 (신뢰도: {result['confidence']:.0%})")
        else:
            print(f"❌ '{msg}' → 매칭 실패 (LLM 폴백 필요)")
    print()

async def test_llm():
    print("3️⃣  LLM Provider 테스트")
    print("-" * 60)
    provider = get_llm_provider()

    test_messages = [
        "할인 있나요?",
        "환불 정책이 어떻게 되나요?",
    ]

    for msg in test_messages:
        result = await provider.generate_response(msg)
        print(f"📝 '{msg}'")
        print(f"   응답: {result['response'][:50]}...")
        print(f"   신뢰도: {result['confidence']:.0%}")
        print(f"   검토 필요: {result['needs_review']}")
    print()

async def test_message_router():
    print("4️⃣  메시지 라우터 테스트 (룰 → LLM 폴백)")
    print("-" * 60)
    router = MessageRouter()

    test_messages = [
        "영업시간 알려주세요",  # 룰 매칭 예상
        "할인 행사 있나요?",    # LLM 폴백 예상
    ]

    for msg in test_messages:
        result = await router.generate_auto_response(msg)
        print(f"💬 '{msg}'")
        print(f"   출처: {result['source']}")
        print(f"   응답: {result['response'][:50]}...")
        print(f"   신뢰도: {result['confidence']:.0%}")
        print()

async def test_reservation():
    print("5️⃣  예약 Provider 테스트")
    print("-" * 60)
    provider = get_reservation_provider()

    reservations = await provider.sync_reservations()
    print(f"✅ 네이버 예약 동기화: {len(reservations)}건")
    for res in reservations:
        print(f"   - {res['customer_name']} ({res['date']} {res['time']})")
    print()

async def test_storage():
    print("6️⃣  Storage Provider 테스트")
    print("-" * 60)
    provider = get_storage_provider()

    # 테스트 데이터
    test_data = [
        {"id": 1, "name": "김철수", "phone": "010-1111-2222"},
        {"id": 2, "name": "이영희", "phone": "010-2222-3333"},
    ]

    # 저장
    success = await provider.sync_to_storage(test_data, "test_reservations")
    if success:
        print("✅ CSV 파일 저장 성공")

    # 읽기
    data = await provider.sync_from_storage("test_reservations")
    print(f"✅ CSV 파일 읽기: {len(data)}건")
    print()

async def main():
    try:
        await test_sms()
        await test_rules()
        await test_llm()
        await test_message_router()
        await test_reservation()
        await test_storage()

        print("=" * 60)
        print("✅ 모든 Mock Provider 테스트 통과!")
        print("=" * 60)
        print()
        print("다음 단계:")
        print("1. 백엔드 서버 실행: uvicorn app.main:app --reload")
        print("2. 프론트엔드 실행: cd frontend && npm run dev")
        print("3. 브라우저에서 http://localhost:5173 접속")
        print()

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
