import { useState, useEffect, useCallback, DragEvent } from 'react';
import { DatePicker, Row, Col, Statistic, Tag, message, Spin, Space, Select, Button } from 'antd';
import { HomeOutlined, CheckCircleOutlined, SendOutlined, ReloadOutlined, CloseOutlined } from '@ant-design/icons';
import { reservationsAPI, campaignsAPI } from '../services/api';
import dayjs, { Dayjs } from 'dayjs';

interface Reservation {
  id: number;
  customer_name: string;
  phone: string;
  date: string;
  time: string;
  status: string;
  room_number: string | null;
  room_password: string | null;
  room_info: string | null;
  gender: string | null;
  party_participants: number | null;
  tags: string | null;
  notes: string | null;
  room_sms_sent: boolean;
  party_sms_sent: boolean;
}

const ALL_ROOMS = [
  'A101', 'A102', 'A103', 'A104', 'A105',
  'B201', 'B202', 'B203', 'B204', 'B205',
];

const ROOM_INFO_MAP: Record<string, string> = {
  A101: '더블룸', A102: '트윈룸', A103: '패밀리룸', A104: '디럭스룸', A105: '스탠다드룸',
  B201: '더블룸', B202: '트윈룸', B203: '패밀리룸', B204: '디럭스룸', B205: '스탠다드룸',
};

// Grid column template for guest area only (room label is separate)
const GUEST_COLS = '56px 120px 40px 40px 72px 1fr 80px';
const ROOM_W = 140; // fixed width for room label area

function getPartyLabel(tags: string | null): string {
  if (!tags) return '';
  const t = tags.split(',').map((s) => s.trim());
  const has1 = t.some((v) => v === '1초');
  const has2 = t.some((v) => v === '2차만');
  if (has1 && has2) return '2';
  if (has1) return '1';
  if (has2) return '2차만';
  return '';
}

function smsLabel(res: Reservation): string {
  const parts: string[] = [];
  if (res.room_sms_sent) parts.push('객실O');
  if (res.party_sms_sent) parts.push('파티O');
  return parts.join(' ');
}

const CELL: React.CSSProperties = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  fontSize: 13,
  lineHeight: '32px',
};

const TAG_OPTIONS = ['객후', '1초', '2차만', '객후,1초', '1초,2차만'];
const SMS_TYPES = [
  { value: 'room', label: '객실 문자' },
  { value: 'party', label: '파티 문자' },
];

const RoomAssignment = () => {
  const [selectedDate, setSelectedDate] = useState<Dayjs>(dayjs());
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(false);
  const [dragOverRoom, setDragOverRoom] = useState<string | null>(null);
  const [dragOverPool, setDragOverPool] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Campaign sending state
  const [selectedTag, setSelectedTag] = useState<string>('객후');
  const [smsType, setSmsType] = useState<string>('room');
  const [targets, setTargets] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [guideSending, setGuideSending] = useState(false);

  const fetchReservations = useCallback(async (date: Dayjs) => {
    setLoading(true);
    try {
      const res = await reservationsAPI.getAll({ date: date.format('YYYY-MM-DD'), limit: 200 });
      setReservations(res.data);
    } catch {
      message.error('예약 목록을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReservations(selectedDate);
    setTargets([]);
  }, [selectedDate, fetchReservations]);

  // --- Campaign functions ---
  useEffect(() => {
    campaignsAPI.getTemplates().then((res) => {
      setTemplates(res.data);
      if (res.data.length > 0) setSelectedTemplate(res.data[0].key);
    }).catch(() => {});
  }, []);

  const loadTargets = async () => {
    setTargetsLoading(true);
    try {
      const response = await campaignsAPI.getTargets(selectedTag, smsType, selectedDate.format('YYYY-MM-DD'));
      setTargets(response.data.targets || []);
    } catch {
      message.error('대상자 조회 실패');
    } finally {
      setTargetsLoading(false);
    }
  };

  const handleSendCampaign = async () => {
    if (!selectedTag || !selectedTemplate) {
      message.warning('태그와 템플릿을 선택하세요');
      return;
    }
    setSending(true);
    try {
      const response = await campaignsAPI.sendByTag({
        tag: selectedTag,
        template_key: selectedTemplate,
        sms_type: smsType,
        date: selectedDate.format('YYYY-MM-DD'),
      });
      message.success(`발송 완료: ${response.data.sent_count}건 성공`);
      loadTargets();
    } catch {
      message.error('발송 실패');
    } finally {
      setSending(false);
    }
  };

  const handleSendRoomGuide = async () => {
    setGuideSending(true);
    try {
      const response = await campaignsAPI.sendRoomGuide({ date: selectedDate.format('YYYY-MM-DD') });
      message.success(`객실 안내 발송 완료: ${response.data.sent_count}건`);
    } catch {
      message.error('객실 안내 발송 실패');
    } finally {
      setGuideSending(false);
    }
  };

  const handleSendPartyGuide = async () => {
    setGuideSending(true);
    try {
      const response = await campaignsAPI.sendPartyGuide({ date: selectedDate.format('YYYY-MM-DD') });
      message.success(`파티 안내 발송 완료: ${response.data.sent_count}건`);
    } catch {
      message.error('파티 안내 발송 실패');
    } finally {
      setGuideSending(false);
    }
  };

  const assignedRooms = new Map<string, Reservation>();
  reservations.forEach((r) => {
    if (r.room_number) assignedRooms.set(r.room_number, r);
  });
  const unassigned = reservations.filter((r) => !r.room_number);

  // --- Drag handlers ---
  const onDragStart = (e: DragEvent, resId: number) => {
    e.dataTransfer.setData('text/plain', String(resId));
    e.dataTransfer.effectAllowed = 'move';
  };

  const onRoomDragOver = (e: DragEvent, room: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverRoom(room);
  };
  const onRoomDragLeave = () => setDragOverRoom(null);

  const onRoomDrop = async (e: DragEvent, room: string) => {
    e.preventDefault();
    setDragOverRoom(null);
    const resId = Number(e.dataTransfer.getData('text/plain'));
    if (!resId) return;
    const current = assignedRooms.get(room);
    if (current?.id === resId) return;

    setProcessing(true);
    try {
      if (current) await reservationsAPI.assignRoom(current.id, { room_number: null });
      await reservationsAPI.assignRoom(resId, { room_number: room });
      message.success(`${room} 배정 완료`);
      await fetchReservations(selectedDate);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '객실 배정에 실패했습니다.');
    } finally {
      setProcessing(false);
    }
  };

  const onPoolDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverPool(true);
  };
  const onPoolDragLeave = () => setDragOverPool(false);

  const onPoolDrop = async (e: DragEvent) => {
    e.preventDefault();
    setDragOverPool(false);
    const resId = Number(e.dataTransfer.getData('text/plain'));
    if (!resId) return;
    const res = reservations.find((r) => r.id === resId);
    if (!res?.room_number) return;

    setProcessing(true);
    try {
      await reservationsAPI.assignRoom(resId, { room_number: null });
      message.success('배정 해제 완료');
      await fetchReservations(selectedDate);
    } catch {
      message.error('배정 해제에 실패했습니다.');
    } finally {
      setProcessing(false);
    }
  };

  const assignedCount = reservations.filter((r) => r.room_number).length;

  // --- Room row: room label (fixed) + guest area (colored) ---
  const renderRoomRow = (room: string) => {
    const res = assignedRooms.get(room);
    const isDragOver = dragOverRoom === room;
    const genderPeople = res ? [res.gender, res.party_participants].filter(Boolean).join('') : '';
    const party = res ? getPartyLabel(res.tags) : '';
    const sms = res ? smsLabel(res) : '';

    return (
      <div
        key={room}
        onDragOver={(e) => onRoomDragOver(e, room)}
        onDragLeave={onRoomDragLeave}
        onDrop={(e) => onRoomDrop(e, room)}
        style={{
          display: 'flex',
          marginBottom: 2,
          borderRadius: 4,
          overflow: 'hidden',
          minHeight: 40,
          userSelect: 'none',
          border: '1px solid #f0f0f0',
        }}
      >
        {/* Room label — always neutral */}
        <div style={{
          width: ROOM_W,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '4px 12px',
          background: '#fafafa',
          borderRight: '1px solid #f0f0f0',
        }}>
          <strong style={{ fontSize: 14 }}>{room}</strong>
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>{ROOM_INFO_MAP[room]}</span>
        </div>

        {/* Guest area — colored, draggable, drop target */}
        <div
          draggable={!!res}
          onDragStart={(e) => res && onDragStart(e, res.id)}
          style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: GUEST_COLS,
            gap: 8,
            padding: '4px 12px',
            alignItems: 'center',
            background: isDragOver
              ? '#e6f7ff'
              : res ? '#f6ffed' : '#fff',
            borderLeft: isDragOver
              ? '3px solid #1890ff'
              : res ? '3px solid #b7eb8f' : '3px solid transparent',
            transition: 'all 0.12s',
            cursor: res ? 'grab' : 'default',
          }}
        >
          {res ? (
            <>
              <div style={CELL}>{res.customer_name}</div>
              <div style={CELL}>{res.phone}</div>
              <div style={{ ...CELL, textAlign: 'center' }}>{genderPeople || '-'}</div>
              <div style={{ ...CELL, textAlign: 'center' }}>{party}</div>
              <div style={CELL}>{res.room_info || '-'}</div>
              <div style={{ ...CELL, color: '#8c8c8c' }}>{res.notes || ''}</div>
              <div style={CELL}>
                {sms ? <Tag color="green" style={{ margin: 0, fontSize: 11 }}>{sms}</Tag> : ''}
              </div>
            </>
          ) : (
            <div style={{ gridColumn: '1 / -1', ...CELL, color: '#bfbfbf' }}>
              {isDragOver ? '여기에 놓으세요' : ''}
            </div>
          )}
        </div>
      </div>
    );
  };

  // --- Draggable card in unassigned pool ---
  const renderPoolCard = (res: Reservation) => {
    const genderPeople = [res.gender, res.party_participants].filter(Boolean).join('');
    const party = getPartyLabel(res.tags);

    return (
      <div
        key={res.id}
        draggable
        onDragStart={(e) => onDragStart(e, res.id)}
        style={{
          padding: '6px 10px',
          background: '#fff',
          border: '1px solid #d9d9d9',
          borderRadius: 6,
          cursor: 'grab',
          fontSize: 12,
          boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
          userSelect: 'none',
        }}
      >
        <div><strong>{res.customer_name}</strong> {res.phone}</div>
        <div style={{ color: '#8c8c8c', marginTop: 2 }}>
          {genderPeople || '-'}
          {party && <> · 파티 {party}</>}
          {res.notes && <> · {res.notes}</>}
        </div>
      </div>
    );
  };

  return (
    <Spin spinning={processing}>
      <div>
        <h2><HomeOutlined /> 객실 배정</h2>

        <Row gutter={16} align="middle" style={{ marginBottom: 20 }}>
          <Col>
            <DatePicker value={selectedDate} onChange={(d) => d && setSelectedDate(d)} style={{ width: 200 }} />
          </Col>
          <Col><Statistic title="총 예약" value={reservations.length} suffix="건" /></Col>
          <Col>
            <Statistic title="배정" value={assignedCount} suffix={`/ ${ALL_ROOMS.length}`} prefix={<CheckCircleOutlined />} />
          </Col>
          <Col>
            <Statistic title="미배정" value={unassigned.length} suffix="건"
              valueStyle={{ color: unassigned.length > 0 ? '#cf1322' : '#3f8600' }} />
          </Col>
        </Row>

        <div style={{
          background: '#fafafa',
          borderRadius: 8,
          padding: '12px 16px',
          marginBottom: 16,
          border: '1px solid #f0f0f0',
        }}>
          <Space wrap>
            <Select
              style={{ width: 130 }}
              value={selectedTag}
              onChange={setSelectedTag}
              options={TAG_OPTIONS.map(t => ({ value: t, label: t }))}
              placeholder="태그"
            />
            <Select
              style={{ width: 130 }}
              value={smsType}
              onChange={setSmsType}
              options={SMS_TYPES}
            />
            <Select
              style={{ width: 170 }}
              value={selectedTemplate}
              onChange={setSelectedTemplate}
              options={templates.map((t: any) => ({ value: t.key, label: t.name }))}
              placeholder="템플릿"
            />
            <Button onClick={loadTargets} loading={targetsLoading} icon={<ReloadOutlined />}>
              대상조회
            </Button>
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSendCampaign}
              loading={sending}
              disabled={targets.length === 0}
            >
              발송 ({targets.length}건)
            </Button>
            <div style={{ width: 1, height: 24, background: '#d9d9d9', margin: '0 4px' }} />
            <Button type="primary" icon={<SendOutlined />} onClick={handleSendRoomGuide} loading={guideSending}>
              객실 안내 발송
            </Button>
            <Button type="primary" icon={<SendOutlined />} onClick={handleSendPartyGuide} loading={guideSending}>
              파티 안내 발송
            </Button>
          </Space>

          {/* Target list — slide down */}
          <div style={{
            maxHeight: targets.length > 0 ? 300 : 0,
            overflow: 'hidden',
            transition: 'max-height 0.3s ease, margin-top 0.3s ease, opacity 0.25s ease',
            opacity: targets.length > 0 ? 1 : 0,
            marginTop: targets.length > 0 ? 12 : 0,
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 6,
            }}>
              <span style={{ fontSize: 13, fontWeight: 500 }}>
                발송 대상 {targets.length}건
              </span>
              <Button
                type="text"
                size="small"
                icon={<CloseOutlined />}
                onClick={() => setTargets([])}
              />
            </div>
            <div style={{
              maxHeight: 250,
              overflowY: 'auto',
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
            }}>
              {targets.map((t: any) => (
                <Tag key={t.id} style={{ margin: 0, fontSize: 12 }}>
                  {t.name} {t.phone} {t.room_number || ''}
                </Tag>
              ))}
            </div>
          </div>
        </div>

        <Row gutter={16}>
          <Col flex="auto">
            <Spin spinning={loading}>
              <div style={{ background: '#fff', borderRadius: 8, padding: '12px 12px 8px', border: '1px solid #f0f0f0' }}>
                {/* Header */}
                <div style={{
                  display: 'flex',
                  borderBottom: '1px solid #f0f0f0',
                  marginBottom: 6,
                  paddingBottom: 6,
                  fontSize: 12,
                  color: '#8c8c8c',
                  fontWeight: 500,
                }}>
                  <div style={{ width: ROOM_W, flexShrink: 0, paddingLeft: 12 }}>객실</div>
                  <div style={{
                    flex: 1,
                    display: 'grid',
                    gridTemplateColumns: GUEST_COLS,
                    gap: 8,
                    paddingLeft: 12,
                  }}>
                    <div>이름</div>
                    <div>전화번호</div>
                    <div style={{ textAlign: 'center' }}>성별</div>
                    <div style={{ textAlign: 'center' }}>파티</div>
                    <div>예약객실</div>
                    <div>메모</div>
                    <div>문자</div>
                  </div>
                </div>
                {ALL_ROOMS.map(renderRoomRow)}
              </div>
            </Spin>
          </Col>

          <Col flex="260px">
            <div
              onDragOver={onPoolDragOver}
              onDragLeave={onPoolDragLeave}
              onDrop={onPoolDrop}
              style={{
                background: dragOverPool ? '#fff1f0' : '#fff',
                borderRadius: 8,
                padding: 12,
                border: dragOverPool ? '2px dashed #ff4d4f' : '1px solid #f0f0f0',
                minHeight: 300,
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>
                미배정 ({unassigned.length})
              </div>
              {unassigned.length === 0 && !loading && (
                <div style={{ color: '#bfbfbf', textAlign: 'center', paddingTop: 40, fontSize: 12 }}>
                  모든 예약이 배정되었거나<br />해당 날짜에 예약이 없습니다
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {unassigned.map(renderPoolCard)}
              </div>
              {dragOverPool && (
                <div style={{ textAlign: 'center', color: '#ff4d4f', marginTop: 12, fontSize: 12 }}>
                  여기에 놓으면 배정 해제
                </div>
              )}
            </div>
          </Col>
        </Row>
      </div>
    </Spin>
  );
};

export default RoomAssignment;
