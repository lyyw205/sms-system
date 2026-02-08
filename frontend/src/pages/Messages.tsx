import { useEffect, useState, useRef, useCallback } from 'react';
import { Input, Button, Tag, Spin, Empty, message as antMessage } from 'antd';
import {
  SendOutlined,
  SearchOutlined,
  ReloadOutlined,
  UserOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { messagesAPI } from '../services/api';

const { TextArea } = Input;

interface Contact {
  phone: string;
  last_message: string;
  last_message_time: string;
  last_direction: string;
  customer_name: string | null;
}

interface MessageItem {
  id: number;
  message_id: string;
  direction: string;
  from_: string;
  to: string;
  message: string;
  status: string;
  created_at: string;
  auto_response: string | null;
  auto_response_confidence: number | null;
  needs_review: boolean;
  response_source: string | null;
}

const OUR_NUMBER = '010-9999-0000';

const QUICK_MESSAGES = [
  { label: '영업시간', text: '영업시간이 어떻게 되나요?' },
  { label: '예약문의', text: '예약하고 싶습니다' },
  { label: '가격문의', text: '가격이 어떻게 되나요?' },
  { label: '주차안내', text: '주차 가능한가요?' },
  { label: '취소문의', text: '예약 취소하고 싶습니다' },
];

const Messages = () => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedPhone, setSelectedPhone] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputText, setInputText] = useState('');
  const [searchText, setSearchText] = useState('');
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadContacts = useCallback(async () => {
    setLoadingContacts(true);
    try {
      const response = await messagesAPI.getContacts();
      setContacts(response.data);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      setLoadingContacts(false);
    }
  }, []);

  const loadMessages = useCallback(async (phone: string) => {
    setLoadingMessages(true);
    try {
      const response = await messagesAPI.getAll({ phone, limit: 200 });
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to load messages:', error);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  useEffect(() => {
    if (selectedPhone) {
      loadMessages(selectedPhone);
    }
  }, [selectedPhone, loadMessages]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSelectContact = (phone: string) => {
    setSelectedPhone(phone);
  };

  const handleSend = async () => {
    if (!inputText.trim() || !selectedPhone) return;

    setSending(true);
    try {
      // Simulate receiving a message from the selected contact
      await messagesAPI.simulateReceive({
        from_: selectedPhone,
        to: OUR_NUMBER,
        message: inputText.trim(),
      });
      setInputText('');
      // Reload both messages and contacts to reflect new messages
      await Promise.all([loadMessages(selectedPhone), loadContacts()]);
    } catch (error) {
      antMessage.error('메시지 전송 실패');
      console.error('Failed to send:', error);
    } finally {
      setSending(false);
    }
  };

  const handleQuickMessage = async (text: string) => {
    if (!selectedPhone) return;
    setInputText(text);
    // Auto-send
    setSending(true);
    try {
      await messagesAPI.simulateReceive({
        from_: selectedPhone,
        to: OUR_NUMBER,
        message: text,
      });
      setInputText('');
      await Promise.all([loadMessages(selectedPhone), loadContacts()]);
    } catch (error) {
      antMessage.error('메시지 전송 실패');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return '방금 전';
    if (diffMin < 60) return `${diffMin}분 전`;
    if (diffHour < 24) return `${diffHour}시간 전`;
    if (diffDay < 7) return `${diffDay}일 전`;
    return date.toLocaleDateString('ko-KR');
  };

  const formatMessageTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
  };

  const filteredContacts = contacts.filter((c) => {
    if (!searchText) return true;
    const search = searchText.toLowerCase();
    return (
      c.phone.includes(search) ||
      (c.customer_name && c.customer_name.toLowerCase().includes(search)) ||
      c.last_message.toLowerCase().includes(search)
    );
  });

  const selectedContact = contacts.find((c) => c.phone === selectedPhone);

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)', background: '#fff' }}>
      {/* Left sidebar - Contact list */}
      <div
        style={{
          width: 320,
          borderRight: '1px solid #e8e8e8',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
        }}
      >
        {/* Sidebar header */}
        <div style={{ padding: '16px', borderBottom: '1px solid #e8e8e8' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <h2 style={{ margin: 0, fontSize: 18 }}>대화</h2>
            <Button
              icon={<ReloadOutlined />}
              size="small"
              onClick={loadContacts}
              loading={loadingContacts}
            />
          </div>
          <Input
            prefix={<SearchOutlined />}
            placeholder="이름 또는 전화번호 검색"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
        </div>

        {/* Contact list */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loadingContacts && contacts.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin />
            </div>
          ) : filteredContacts.length === 0 ? (
            <Empty description="대화 내역이 없습니다" style={{ marginTop: 40 }} />
          ) : (
            filteredContacts.map((contact) => (
              <div
                key={contact.phone}
                onClick={() => handleSelectContact(contact.phone)}
                style={{
                  padding: '12px 16px',
                  cursor: 'pointer',
                  background: selectedPhone === contact.phone ? '#e6f4ff' : 'transparent',
                  borderBottom: '1px solid #f0f0f0',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (selectedPhone !== contact.phone) {
                    e.currentTarget.style.background = '#fafafa';
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedPhone !== contact.phone) {
                    e.currentTarget.style.background = 'transparent';
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: '50%',
                      background: '#1677ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontSize: 16,
                      flexShrink: 0,
                    }}
                  >
                    <UserOutlined />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>
                        {contact.customer_name || contact.phone}
                      </span>
                      <span style={{ fontSize: 11, color: '#999', flexShrink: 0 }}>
                        {formatTime(contact.last_message_time)}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 13,
                        color: '#666',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        marginTop: 2,
                      }}
                    >
                      {contact.last_direction === 'outbound' && (
                        <span style={{ color: '#999' }}>나: </span>
                      )}
                      {contact.last_message}
                    </div>
                    {contact.customer_name && (
                      <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                        {contact.phone}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right side - Chat area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {!selectedPhone ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#999',
              fontSize: 16,
            }}
          >
            왼쪽에서 대화를 선택하세요
          </div>
        ) : (
          <>
            {/* Chat header */}
            <div
              style={{
                padding: '12px 20px',
                borderBottom: '1px solid #e8e8e8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: '#fafafa',
              }}
            >
              <div>
                <span style={{ fontWeight: 600, fontSize: 16 }}>
                  {selectedContact?.customer_name || selectedPhone}
                </span>
                {selectedContact?.customer_name && (
                  <span style={{ marginLeft: 8, fontSize: 13, color: '#666' }}>
                    {selectedPhone}
                  </span>
                )}
              </div>
              <Button
                icon={<ReloadOutlined />}
                size="small"
                onClick={() => loadMessages(selectedPhone)}
                loading={loadingMessages}
              >
                새로고침
              </Button>
            </div>

            {/* Messages area */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '16px 20px',
                background: '#f5f5f5',
              }}
            >
              {loadingMessages && messages.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 40 }}>
                  <Spin />
                </div>
              ) : messages.length === 0 ? (
                <Empty description="메시지가 없습니다" />
              ) : (
                messages.map((msg) => {
                  const isOutbound = msg.direction === 'outbound';

                  return (
                    <div
                      key={msg.id}
                      style={{
                        display: 'flex',
                        justifyContent: isOutbound ? 'flex-end' : 'flex-start',
                        marginBottom: 12,
                      }}
                    >
                      <div style={{ maxWidth: '70%' }}>
                        {/* Message bubble */}
                        <div
                          style={{
                            padding: '10px 14px',
                            borderRadius: isOutbound
                              ? '16px 4px 16px 16px'
                              : '4px 16px 16px 16px',
                            background: isOutbound ? '#1677ff' : '#fff',
                            color: isOutbound ? '#fff' : '#333',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
                            fontSize: 14,
                            lineHeight: 1.5,
                            wordBreak: 'break-word',
                          }}
                        >
                          {msg.message}
                        </div>

                        {/* Meta info below bubble */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            marginTop: 4,
                            justifyContent: isOutbound ? 'flex-end' : 'flex-start',
                            flexWrap: 'wrap',
                          }}
                        >
                          <span style={{ fontSize: 11, color: '#999' }}>
                            {formatMessageTime(msg.created_at)}
                          </span>

                          {/* Source tag for outbound */}
                          {isOutbound && msg.response_source && (
                            <Tag
                              color={
                                msg.response_source === 'rule'
                                  ? 'green'
                                  : msg.response_source === 'llm'
                                  ? 'blue'
                                  : 'orange'
                              }
                              style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}
                            >
                              {msg.response_source}
                            </Tag>
                          )}

                          {/* Confidence for outbound auto-responses */}
                          {isOutbound && msg.auto_response_confidence && (
                            <span style={{ fontSize: 11, color: '#999' }}>
                              {(msg.auto_response_confidence * 100).toFixed(0)}%
                            </span>
                          )}

                          {/* Needs review tag for inbound */}
                          {!isOutbound && msg.needs_review && (
                            <Tag
                              color="red"
                              icon={<ExclamationCircleOutlined />}
                              style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}
                            >
                              검토 필요
                            </Tag>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input area */}
            <div
              style={{
                borderTop: '1px solid #e8e8e8',
                background: '#fff',
                padding: '8px 16px 12px',
              }}
            >
              {/* Quick message buttons */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                {QUICK_MESSAGES.map((qm) => (
                  <Button
                    key={qm.label}
                    size="small"
                    style={{ borderRadius: 16, fontSize: 12 }}
                    onClick={() => handleQuickMessage(qm.text)}
                    disabled={sending}
                  >
                    {qm.label}
                  </Button>
                ))}
              </div>

              {/* Text input + send button */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                <TextArea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="메시지를 입력하세요... (Enter로 전송)"
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  style={{ flex: 1, borderRadius: 8 }}
                  disabled={sending}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  loading={sending}
                  disabled={!inputText.trim()}
                  style={{ borderRadius: 8, height: 36 }}
                >
                  전송
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default Messages;
