import { useState, useEffect, useCallback, DragEvent, useMemo } from 'react';
import { DatePicker, Row, Col, Statistic, Tag, message, Spin, Space, Select, Button, Modal, Form, Input, InputNumber } from 'antd';
import { HomeOutlined, CheckCircleOutlined, SendOutlined, ReloadOutlined, CloseOutlined, UserAddOutlined, EditOutlined, DeleteOutlined, SettingOutlined, SaveOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { reservationsAPI, campaignsAPI, roomsAPI } from '../services/api';
import { useNavigate } from 'react-router-dom';
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
  sent_sms_types: string | null;  // "객후,파티안내,객실안내"
}

const TAG_OPTIONS = ['1초', '2차만', '객후', '파티만', '객후,1초', '1초,2차만'];
const ROOM_TYPE_OPTIONS = ['더블룸', '트윈룸', '패밀리룸', '디럭스룸', '스탠다드룸'];

// Grid column template for guest area only (room label is separate)
const GUEST_COLS = '56px 120px 40px 40px 72px 1fr 60px 80px'; // Added separate SMS and Action columns
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

// SMS 상태를 계산하는 함수 (예정/완료 구분)
function getSmsStatus(res: Reservation): { pending: string[], sent: string[] } {
  const pending: string[] = [];
  const sent: string[] = [];

  // 이미 발송된 SMS 타입들
  const sentTypes = res.sent_sms_types ? res.sent_sms_types.split(',').map(s => s.trim()) : [];

  // 1. 객후: 메모에 "객후" 텍스트가 있으면 예정 or 발송완료
  if (res.notes?.includes('객후')) {
    if (sentTypes.includes('객후')) {
      sent.push('객후');
    } else {
      pending.push('객후');
    }
  }

  // 2. 객실안내: room_number가 있으면 예정 or 발송완료
  if (res.room_number) {
    if (sentTypes.includes('객실안내') || res.room_sms_sent) {
      sent.push('객실안내');
    } else {
      pending.push('객실안내');
    }
  }

  // 3. 파티안내: 파티 참여자면 예정 or 발송완료
  // 파티만 게스트이거나 파티 참여가 있는 경우
  const isPartyGuest = !res.room_number && res.tags?.includes('파티만');
  if (isPartyGuest || res.party_participants) {
    if (sentTypes.includes('파티안내') || res.party_sms_sent) {
      sent.push('파티안내');
    } else {
      pending.push('파티안내');
    }
  }

  return { pending, sent };
}

const CELL: React.CSSProperties = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  fontSize: 13,
  lineHeight: '32px',
};


const RoomAssignment = () => {
  const navigate = useNavigate();
  const [selectedDate, setSelectedDate] = useState<Dayjs>(dayjs());
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [rooms, setRooms] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [dragOverRoom, setDragOverRoom] = useState<string | null>(null);
  const [dragOverPool, setDragOverPool] = useState(false);
  const [dragOverPartyZone, setDragOverPartyZone] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Modal and form state for CRUD operations
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  // Inline editing state
  const [inlineEditingId, setInlineEditingId] = useState<number | null>(null);
  const [inlineEditValues, setInlineEditValues] = useState<any>({});

  // Build room info map from loaded rooms
  const roomInfoMap = useMemo(() => {
    const map: Record<string, string> = {};
    rooms.forEach(room => {
      map[room.room_number] = room.room_type;
    });
    return map;
  }, [rooms]);

  // Get active room numbers sorted by sort_order
  const activeRoomNumbers = useMemo(() => {
    return rooms
      .filter(room => room.is_active)
      .map(room => room.room_number);
  }, [rooms]);

  // Independent campaign state
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<string>('');
  const [targets, setTargets] = useState<any[]>([]);
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [guideSending, setGuideSending] = useState(false);

  const fetchRooms = useCallback(async () => {
    try {
      const res = await roomsAPI.getAll();
      setRooms(res.data);
    } catch {
      message.error('객실 목록을 불러오지 못했습니다.');
    }
  }, []);

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
    fetchRooms();
  }, [fetchRooms]);

  useEffect(() => {
    fetchReservations(selectedDate);
    setTargets([]);
  }, [selectedDate, fetchReservations]);

  // --- Load campaign list ---
  useEffect(() => {
    campaignsAPI.getList().then((res) => {
      setCampaigns(res.data);
      if (res.data.length > 0) setSelectedCampaign(res.data[0].id);
    }).catch(() => {
      message.error('캠페인 목록 로드 실패');
    });
  }, []);

  const loadTargets = async () => {
    if (!selectedCampaign) {
      message.warning('캠페인을 선택하세요');
      return;
    }
    setTargetsLoading(true);
    try {
      const response = await campaignsAPI.preview(selectedCampaign, selectedDate.format('YYYY-MM-DD'));
      setTargets(response.data.targets || []);
    } catch {
      message.error('대상자 조회 실패');
    } finally {
      setTargetsLoading(false);
    }
  };

  const handleSendCampaign = async () => {
    if (!selectedCampaign) {
      message.warning('캠페인을 선택하세요');
      return;
    }
    setSending(true);
    try {
      const response = await campaignsAPI.send({
        campaign_type: selectedCampaign,
        date: selectedDate.format('YYYY-MM-DD'),
      });
      message.success(`발송 완료: ${response.data.sent_count}건 성공`);
      await loadTargets();
      await fetchReservations(selectedDate);
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

  // Guest classification logic
  const { assignedRooms, unassigned, partyOnly } = useMemo(() => {
    const assigned = new Map<string, Reservation>();
    const unassignedList: Reservation[] = [];
    const partyOnlyList: Reservation[] = [];

    reservations.forEach((res) => {
      if (res.room_number) {
        assigned.set(res.room_number, res);
      } else if (res.tags?.includes('파티만')) {
        partyOnlyList.push(res);
      } else {
        unassignedList.push(res);
      }
    });

    return {
      assignedRooms: assigned,
      unassigned: unassignedList,
      partyOnly: partyOnlyList
    };
  }, [reservations]);

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

  // Drop zone handlers for party-only section
  const onPartyZoneDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverPartyZone(true);
  };

  const onPartyZoneDragLeave = () => setDragOverPartyZone(false);

  const onPartyZoneDrop = async (e: DragEvent) => {
    e.preventDefault();
    setDragOverPartyZone(false);
    const resId = Number(e.dataTransfer.getData('text/plain'));
    if (!resId) return;

    const guest = reservations.find(r => r.id === resId);
    if (!guest?.room_number) return; // Already unassigned

    Modal.confirm({
      title: '파티만으로 전환',
      content: '객실 배정을 해제하고 파티만 게스트로 변경하시겠습니까?',
      onOk: async () => {
        setProcessing(true);
        try {
          // Unassign room
          await reservationsAPI.assignRoom(resId, { room_number: null });

          // Add "파티만" tag if not present
          if (!guest.tags?.includes('파티만')) {
            const newTags = guest.tags ? `${guest.tags},파티만` : '파티만';
            await reservationsAPI.update(resId, { tags: newTags });
          }

          message.success('파티만으로 전환 완료');
          await fetchReservations(selectedDate);
        } catch {
          message.error('전환 실패');
        } finally {
          setProcessing(false);
        }
      }
    });
  };

  const assignedCount = reservations.filter((r) => r.room_number).length;

  // CRUD operation handlers
  const handleAddPartyGuest = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      date: selectedDate.format('YYYY-MM-DD'),
      time: '18:00',
      status: 'confirmed',
      source: 'manual',
      tags: '파티만',  // Auto-tag as party-only
    });
    setModalVisible(true);
  };

  const handleEditGuest = (id: number) => {
    const guest = reservations.find(r => r.id === id);
    if (guest) {
      setEditingId(id);
      form.setFieldsValue({
        ...guest,
        tags: guest.tags || '',
      });
      setModalVisible(true);
    }
  };

  const handleDeleteGuest = (id: number) => {
    Modal.confirm({
      title: '게스트 삭제',
      content: '정말 삭제하시겠습니까?',
      onOk: async () => {
        try {
          await reservationsAPI.delete(id);
          message.success('삭제 완료');
          fetchReservations(selectedDate);
        } catch {
          message.error('삭제 실패');
        }
      }
    });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      // Ensure "파티만" tag for party-only guests (when no room is assigned)
      if (!values.room_number && !values.tags?.includes('파티만')) {
        values.tags = values.tags ? `${values.tags},파티만` : '파티만';
      }

      if (editingId) {
        await reservationsAPI.update(editingId, values);
        message.success('수정 완료');
      } else {
        await reservationsAPI.create(values);
        message.success('추가 완료');
      }

      setModalVisible(false);
      fetchReservations(selectedDate);
    } catch (error) {
      message.error('저장 실패');
    }
  };

  // Inline editing handlers
  const handleInlineEdit = (res: Reservation) => {
    setInlineEditingId(res.id);
    setInlineEditValues({
      customer_name: res.customer_name,
      phone: res.phone,
      gender: res.gender,
      party_participants: res.party_participants,
      room_info: res.room_info,
      notes: res.notes,
      tags: res.tags,
    });
  };

  const handleInlineSave = async () => {
    if (!inlineEditingId) return;

    try {
      await reservationsAPI.update(inlineEditingId, inlineEditValues);
      message.success('수정 완료');
      setInlineEditingId(null);
      setInlineEditValues({});
      fetchReservations(selectedDate);
    } catch (error) {
      message.error('저장 실패');
    }
  };

  const handleInlineCancel = () => {
    setInlineEditingId(null);
    setInlineEditValues({});
  };

  // SMS 발송 완료 처리
  const handleSmsComplete = async (res: Reservation, smsType: string) => {
    try {
      const currentTypes = res.sent_sms_types ? res.sent_sms_types.split(',').map(s => s.trim()) : [];

      // 이미 발송 완료된 경우 무시
      if (currentTypes.includes(smsType)) {
        return;
      }

      // 새로운 타입 추가
      const newTypes = [...currentTypes, smsType].join(',');

      await reservationsAPI.update(res.id, { sent_sms_types: newTypes });
      message.success(`${smsType} 발송 완료 처리됨`);
      fetchReservations(selectedDate);
    } catch (error) {
      message.error('발송 완료 처리 실패');
    }
  };

  // --- Room row: room label (fixed) + guest area (colored) ---
  const renderRoomRow = (room: string) => {
    const res = assignedRooms.get(room);
    const isDragOver = dragOverRoom === room;
    const isEditing = res && inlineEditingId === res.id;
    const genderPeople = res ? [res.gender, res.party_participants].filter(Boolean).join('') : '';
    const party = res ? getPartyLabel(res.tags) : '';
    const smsStatus = res ? getSmsStatus(res) : { pending: [], sent: [] };

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
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>{roomInfoMap[room] || ''}</span>
        </div>

        {/* Guest area — colored, draggable, drop target */}
        <div
          draggable={!!res && !isEditing}
          onDragStart={(e) => res && !isEditing && onDragStart(e, res.id)}
          style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: GUEST_COLS,
            gap: 8,
            padding: '4px 12px',
            alignItems: 'center',
            background: isDragOver
              ? '#e6f7ff'
              : isEditing
              ? '#fffbe6'
              : res ? '#f6ffed' : '#fff',
            borderLeft: isDragOver
              ? '3px solid #1890ff'
              : isEditing
              ? '3px solid #faad14'
              : res ? '3px solid #b7eb8f' : '3px solid transparent',
            transition: 'all 0.12s',
            cursor: res && !isEditing ? 'grab' : 'default',
          }}
        >
          {res ? (
            isEditing ? (
              // Editing mode
              <>
                <div style={CELL}>
                  <Input
                    size="small"
                    value={inlineEditValues.customer_name}
                    onChange={(e) => setInlineEditValues({ ...inlineEditValues, customer_name: e.target.value })}
                  />
                </div>
                <div style={CELL}>
                  <Input
                    size="small"
                    value={inlineEditValues.phone}
                    onChange={(e) => setInlineEditValues({ ...inlineEditValues, phone: e.target.value })}
                  />
                </div>
                <div style={{ ...CELL, textAlign: 'center' }}>
                  <Select
                    size="small"
                    value={inlineEditValues.gender}
                    onChange={(value) => setInlineEditValues({ ...inlineEditValues, gender: value })}
                    style={{ width: 50 }}
                  >
                    <Select.Option value="남">남</Select.Option>
                    <Select.Option value="여">여</Select.Option>
                  </Select>
                  <InputNumber
                    size="small"
                    value={inlineEditValues.party_participants}
                    onChange={(value) => setInlineEditValues({ ...inlineEditValues, party_participants: value })}
                    min={1}
                    style={{ width: 40, marginLeft: 2 }}
                  />
                </div>
                <div style={{ ...CELL, textAlign: 'center' }}>{party}</div>
                <div style={CELL}>
                  <Select
                    size="small"
                    value={inlineEditValues.room_info}
                    onChange={(value) => setInlineEditValues({ ...inlineEditValues, room_info: value })}
                    style={{ width: 90 }}
                    allowClear
                  >
                    {ROOM_TYPE_OPTIONS.map(type => (
                      <Select.Option key={type} value={type}>{type}</Select.Option>
                    ))}
                  </Select>
                </div>
                <div style={CELL}>
                  <Input
                    size="small"
                    value={inlineEditValues.notes}
                    onChange={(e) => setInlineEditValues({ ...inlineEditValues, notes: e.target.value })}
                  />
                </div>
                <div style={CELL}>
                  <Space size={4} wrap>
                    {smsStatus.pending.map(type => (
                      <Tag
                        key={type}
                        color="default"
                        style={{ margin: 0, fontSize: 10, cursor: 'pointer' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSmsComplete(res, type);
                        }}
                      >
                        {type}
                      </Tag>
                    ))}
                    {smsStatus.sent.map(type => (
                      <Tag key={type} color="green" style={{ margin: 0, fontSize: 10 }}>{type}</Tag>
                    ))}
                    {smsStatus.pending.length === 0 && smsStatus.sent.length === 0 && '-'}
                  </Space>
                </div>
                <div style={CELL}>
                  <Space size={4}>
                    <Button
                      type="primary"
                      size="small"
                      icon={<SaveOutlined />}
                      onClick={handleInlineSave}
                    />
                    <Button
                      size="small"
                      icon={<CloseCircleOutlined />}
                      onClick={handleInlineCancel}
                    />
                  </Space>
                </div>
              </>
            ) : (
              // Display mode
              <>
                <div style={CELL}>{res.customer_name}</div>
                <div style={CELL}>{res.phone}</div>
                <div style={{ ...CELL, textAlign: 'center' }}>{genderPeople || '-'}</div>
                <div style={{ ...CELL, textAlign: 'center' }}>{party}</div>
                <div style={CELL}>{res.room_info || '-'}</div>
                <div style={{ ...CELL, color: '#8c8c8c' }}>{res.notes || ''}</div>
                <div style={CELL}>
                  <Space size={4} wrap>
                    {smsStatus.pending.map(type => (
                      <Tag
                        key={type}
                        color="default"
                        style={{ margin: 0, fontSize: 10, cursor: 'pointer' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSmsComplete(res, type);
                        }}
                      >
                        {type}
                      </Tag>
                    ))}
                    {smsStatus.sent.map(type => (
                      <Tag key={type} color="green" style={{ margin: 0, fontSize: 10 }}>{type}</Tag>
                    ))}
                    {smsStatus.pending.length === 0 && smsStatus.sent.length === 0 && '-'}
                  </Space>
                </div>
                <div style={CELL}>
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInlineEdit(res);
                    }}
                    style={{ padding: '0 4px', height: 20 }}
                  />
                </div>
              </>
            )
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

  // --- Row format for party-only guests (same as room rows) ---
  const renderPartyOnlyRow = (res: Reservation, index: number) => {
    const isEditing = inlineEditingId === res.id;
    const genderPeople = [res.gender, res.party_participants].filter(Boolean).join('');
    const party = getPartyLabel(res.tags);
    const smsStatus = getSmsStatus(res);

    return (
      <div
        key={res.id}
        draggable={!isEditing}
        onDragStart={(e) => !isEditing && onDragStart(e, res.id)}
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
        {/* Empty column (matching room label style) */}
        <div style={{
          width: ROOM_W,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '4px 12px',
          background: '#fafafa',
          borderRight: '1px solid #f0f0f0',
        }}>
          {/* Empty - no label */}
        </div>

        {/* Guest info area */}
        <div
          style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: GUEST_COLS,
            gap: 8,
            padding: '4px 12px',
            alignItems: 'center',
            background: isEditing ? '#fffbe6' : '#f9f0ff',
            borderLeft: isEditing ? '3px solid #faad14' : '3px solid #722ed1',
            transition: 'all 0.12s',
            cursor: isEditing ? 'default' : 'grab',
          }}
        >
          {isEditing ? (
            // Editing mode
            <>
              <div style={CELL}>
                <Input
                  size="small"
                  value={inlineEditValues.customer_name}
                  onChange={(e) => setInlineEditValues({ ...inlineEditValues, customer_name: e.target.value })}
                />
              </div>
              <div style={CELL}>
                <Input
                  size="small"
                  value={inlineEditValues.phone}
                  onChange={(e) => setInlineEditValues({ ...inlineEditValues, phone: e.target.value })}
                />
              </div>
              <div style={{ ...CELL, textAlign: 'center' }}>
                <Select
                  size="small"
                  value={inlineEditValues.gender}
                  onChange={(value) => setInlineEditValues({ ...inlineEditValues, gender: value })}
                  style={{ width: 50 }}
                >
                  <Select.Option value="남">남</Select.Option>
                  <Select.Option value="여">여</Select.Option>
                </Select>
                <InputNumber
                  size="small"
                  value={inlineEditValues.party_participants}
                  onChange={(value) => setInlineEditValues({ ...inlineEditValues, party_participants: value })}
                  min={1}
                  style={{ width: 40, marginLeft: 2 }}
                />
              </div>
              <div style={{ ...CELL, textAlign: 'center' }}>{party}</div>
              <div style={CELL}>
                <Select
                  size="small"
                  value={inlineEditValues.room_info}
                  onChange={(value) => setInlineEditValues({ ...inlineEditValues, room_info: value })}
                  style={{ width: 90 }}
                  allowClear
                >
                  {ROOM_TYPE_OPTIONS.map(type => (
                    <Select.Option key={type} value={type}>{type}</Select.Option>
                  ))}
                </Select>
              </div>
              <div style={CELL}>
                <Input
                  size="small"
                  value={inlineEditValues.notes}
                  onChange={(e) => setInlineEditValues({ ...inlineEditValues, notes: e.target.value })}
                />
              </div>
              <div style={CELL}>
                <Space size={4} wrap>
                  {smsStatus.pending.map(type => (
                    <Tag
                      key={type}
                      color="default"
                      style={{ margin: 0, fontSize: 10, cursor: 'pointer' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSmsComplete(res, type);
                      }}
                    >
                      {type}
                    </Tag>
                  ))}
                  {smsStatus.sent.map(type => (
                    <Tag key={type} color="green" style={{ margin: 0, fontSize: 10 }}>{type}</Tag>
                  ))}
                  {smsStatus.pending.length === 0 && smsStatus.sent.length === 0 && '-'}
                </Space>
              </div>
              <div style={CELL}>
                <Space size={4}>
                  <Button
                    type="primary"
                    size="small"
                    icon={<SaveOutlined />}
                    onClick={handleInlineSave}
                  />
                  <Button
                    size="small"
                    icon={<CloseCircleOutlined />}
                    onClick={handleInlineCancel}
                  />
                </Space>
              </div>
            </>
          ) : (
            // Display mode
            <>
              <div style={CELL}>{res.customer_name}</div>
              <div style={CELL}>{res.phone}</div>
              <div style={{ ...CELL, textAlign: 'center' }}>{genderPeople || '-'}</div>
              <div style={{ ...CELL, textAlign: 'center' }}>{party}</div>
              <div style={CELL}>파티만</div>
              <div style={{ ...CELL, color: '#8c8c8c' }}>{res.notes || ''}</div>
              <div style={CELL}>
                <Space size={4} wrap>
                  {smsStatus.pending.map(type => (
                    <Tag
                      key={type}
                      color="default"
                      style={{ margin: 0, fontSize: 10, cursor: 'pointer' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSmsComplete(res, type);
                      }}
                    >
                      {type}
                    </Tag>
                  ))}
                  {smsStatus.sent.map(type => (
                    <Tag key={type} color="green" style={{ margin: 0, fontSize: 10 }}>{type}</Tag>
                  ))}
                  {smsStatus.pending.length === 0 && smsStatus.sent.length === 0 && '-'}
                </Space>
              </div>
              <div style={CELL}>
                <Space size={4}>
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInlineEdit(res);
                    }}
                    style={{ padding: '0 4px', height: 20 }}
                  />
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteGuest(res.id);
                    }}
                    style={{ padding: '0 4px', height: 20 }}
                  />
                </Space>
              </div>
            </>
          )}
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
            <Space>
              <DatePicker value={selectedDate} onChange={(d) => d && setSelectedDate(d)} style={{ width: 200 }} />
              <Button
                icon={<UserAddOutlined />}
                onClick={handleAddPartyGuest}
              >
                파티만 추가
              </Button>
              <Button
                icon={<SettingOutlined />}
                onClick={() => navigate('/rooms/manage')}
              >
                객실 관리
              </Button>
            </Space>
          </Col>
        </Row>

        <Row gutter={16} align="middle" style={{ marginBottom: 20 }}>
          <Col><Statistic title="총 예약" value={reservations.length} suffix="건" /></Col>
          <Col>
            <Statistic title="배정" value={assignedCount} suffix={`/ ${activeRoomNumbers.length}`} prefix={<CheckCircleOutlined />} />
          </Col>
          <Col>
            <Statistic title="미배정" value={unassigned.length} suffix="건"
              valueStyle={{ color: unassigned.length > 0 ? '#cf1322' : '#3f8600' }} />
          </Col>
          <Col>
            <Statistic
              title="파티만"
              value={partyOnly.length}
              suffix="명"
              valueStyle={{ color: '#722ed1' }}
            />
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
              style={{ width: 200 }}
              value={selectedCampaign}
              onChange={setSelectedCampaign}
              placeholder="캠페인 선택"
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            >
              {campaigns.map((campaign: any) => (
                <Select.Option key={campaign.id} value={campaign.id} label={campaign.name}>
                  {campaign.name}
                </Select.Option>
              ))}
            </Select>
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
              {/* Room Grid */}
              <div style={{ background: '#fff', borderRadius: 8, padding: '12px 12px 8px', border: '1px solid #f0f0f0', marginBottom: 16 }}>
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
                    <div>작업</div>
                  </div>
                </div>
                {activeRoomNumbers.map(renderRoomRow)}
              </div>

              {/* Party-Only Section */}
              <div
                onDragOver={onPartyZoneDragOver}
                onDragLeave={onPartyZoneDragLeave}
                onDrop={onPartyZoneDrop}
                style={{
                  background: '#fff',
                  borderRadius: 8,
                  padding: '12px 12px 8px',
                  border: dragOverPartyZone ? '2px dashed #722ed1' : '1px solid #d3adf7',
                  transition: 'all 0.2s',
                }}
              >
                {/* Header */}
                <div style={{
                  display: 'flex',
                  borderBottom: '1px solid #d3adf7',
                  marginBottom: 6,
                  paddingBottom: 6,
                  fontSize: 12,
                  color: '#722ed1',
                  fontWeight: 600,
                }}>
                  <div style={{ width: ROOM_W, flexShrink: 0, paddingLeft: 12 }}>
                    파티만 게스트 ({partyOnly.length}명)
                  </div>
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
                    <div>구분</div>
                    <div>메모</div>
                    <div>문자</div>
                    <div>작업</div>
                  </div>
                </div>

                {/* Party-only guest rows */}
                {partyOnly.length === 0 ? (
                  <div style={{
                    color: dragOverPartyZone ? '#722ed1' : '#bfbfbf',
                    textAlign: 'center',
                    padding: '40px 20px',
                    fontSize: 13,
                    background: dragOverPartyZone ? '#f9f0ff' : 'transparent',
                    borderRadius: 4,
                    transition: 'all 0.2s',
                  }}>
                    {dragOverPartyZone ? '여기에 놓으면 파티만 게스트로 전환됩니다' : '파티만 게스트가 없습니다'}
                  </div>
                ) : (
                  partyOnly.map((res, idx) => renderPartyOnlyRow(res, idx))
                )}
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

        {/* Guest Form Modal */}
        <Modal
          title={editingId ? '게스트 수정' : '파티만 게스트 추가'}
          open={modalVisible}
          onOk={handleSubmit}
          onCancel={() => setModalVisible(false)}
          width={600}
        >
          <Form form={form} layout="vertical">
            <Form.Item
              name="customer_name"
              label="이름"
              rules={[{ required: true, message: '이름을 입력하세요' }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="phone"
              label="전화번호"
              rules={[{ required: true, message: '전화번호를 입력하세요' }]}
            >
              <Input placeholder="010-1234-5678" />
            </Form.Item>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="date"
                  label="날짜"
                  rules={[{ required: true }]}
                >
                  <Input type="date" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="time"
                  label="시간"
                  rules={[{ required: true }]}
                >
                  <Input type="time" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="gender"
                  label="성별"
                >
                  <Select placeholder="성별 선택">
                    <Select.Option value="남">남</Select.Option>
                    <Select.Option value="여">여</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="party_participants"
                  label="참여 인원"
                  initialValue={1}
                >
                  <Input type="number" min={1} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="room_info"
              label="예약 객실"
              tooltip="최초 예약한 객실 타입 (방 배정과 관계없이 유지됨)"
            >
              <Select
                placeholder="예약 객실 타입 선택"
                allowClear
                options={ROOM_TYPE_OPTIONS.map(type => ({ value: type, label: type }))}
              />
            </Form.Item>
            <Form.Item
              name="tags"
              label="태그"
              tooltip="쉼표로 구분하여 입력 (예: 1초,2차만,파티만)"
            >
              <Select
                mode="tags"
                placeholder="태그 선택 또는 입력"
                options={TAG_OPTIONS.map(tag => ({ value: tag, label: tag }))}
              />
            </Form.Item>
            <Form.Item name="notes" label="메모">
              <Input.TextArea rows={3} placeholder="추가 정보나 요청사항" />
            </Form.Item>
            <Form.Item name="status" hidden initialValue="confirmed">
              <Input />
            </Form.Item>
            <Form.Item name="source" hidden initialValue="manual">
              <Input />
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </Spin>
  );
};

export default RoomAssignment;
