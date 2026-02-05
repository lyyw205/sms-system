import { useState } from 'react';
import { Card, Input, Button, message, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { messagesAPI } from '../services/api';

const { TextArea } = Input;

interface SMSSimulatorProps {
  onSent?: () => void;
}

const SMSSimulator = ({ onSent }: SMSSimulatorProps) => {
  const [from, setFrom] = useState('010-1234-5678');
  const [smsMessage, setSmsMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSimulate = async () => {
    if (!from || !smsMessage) {
      message.error('발신자 번호와 메시지를 입력해주세요');
      return;
    }

    setLoading(true);
    try {
      await messagesAPI.simulateReceive({
        from_: from,
        to: '010-9999-0000',
        message: smsMessage,
      });
      message.success('SMS 수신 시뮬레이션 완료');
      setSmsMessage('');
      if (onSent) onSent();
    } catch (error) {
      message.error('SMS 시뮬레이션 실패');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const quickMessages = [
    '영업시간이 어떻게 되나요?',
    '예약하고 싶어요',
    '가격이 얼마인가요?',
    '주차 가능한가요?',
  ];

  return (
    <Card title="SMS 수신 시뮬레이터 (데모 모드)" style={{ marginBottom: 16 }}>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <label>발신자 번호:</label>
          <Input
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            placeholder="010-1234-5678"
            style={{ marginTop: 8 }}
          />
        </div>
        <div>
          <label>메시지:</label>
          <TextArea
            value={smsMessage}
            onChange={(e) => setSmsMessage(e.target.value)}
            placeholder="메시지를 입력하세요"
            rows={4}
            style={{ marginTop: 8 }}
          />
        </div>
        <div>
          <label>빠른 입력:</label>
          <Space wrap style={{ marginTop: 8 }}>
            {quickMessages.map((msg) => (
              <Button
                key={msg}
                size="small"
                onClick={() => setSmsMessage(msg)}
              >
                {msg}
              </Button>
            ))}
          </Space>
        </div>
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSimulate}
          loading={loading}
          block
        >
          수신 시뮬레이션
        </Button>
      </Space>
    </Card>
  );
};

export default SMSSimulator;
