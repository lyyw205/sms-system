import { useState, useEffect, useCallback, DragEvent, useMemo, useRef } from 'react';
import { reservationsAPI, campaignsAPI, roomsAPI } from '../services/api';
import { useNavigate } from 'react-router-dom';
import dayjs, { Dayjs } from 'dayjs';
import { toast } from 'sonner';
import {
  Badge,
  Button,
  Card,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  TextInput,
  Label,
  Select,
  Spinner,
} from 'flowbite-react';
import {
  Send,
  RefreshCw,
  X,
  UserPlus,
  Pencil,
  Trash2,
  Save,
  XCircle,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

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
  sent_sms_types: string | null; // "객후,파티안내,객실안내"
  source?: string;
}

const TAG_OPTIONS = ['1초', '2차만', '객후', '파티만', '객후,1초', '1초,2차만'];
const ROOM_TYPE_OPTIONS = ['더블룸', '트윈룸', '패밀리룸', '디럭스룸', '스탠다드룸'];


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

function getSmsStatus(res: Reservation): { pending: string[]; sent: string[] } {
  const pending: string[] = [];
  const sent: string[] = [];

  const sentTypes = res.sent_sms_types
    ? res.sent_sms_types.split(',').map((s) => s.trim())
    : [];

  if (res.notes?.includes('객후')) {
    if (sentTypes.includes('객후')) {
      sent.push('객후');
    } else {
      pending.push('객후');
    }
  }

  if (res.room_number) {
    if (sentTypes.includes('객실안내') || res.room_sms_sent) {
      sent.push('객실안내');
    } else {
      pending.push('객실안내');
    }
  }

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

interface SmsCellProps {
  smsStatus: { pending: string[]; sent: string[] };
  isEditing: boolean;
  onToggle?: (smsType: string) => void;
}

const SmsCell: React.FC<SmsCellProps> = ({ smsStatus, isEditing, onToggle }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showArrows, setShowArrows] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = useCallback(() => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setShowArrows(scrollWidth > clientWidth);
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 1);
    }
  }, []);

  useEffect(() => {
    checkScroll();
    const handleResize = () => checkScroll();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [checkScroll, smsStatus]);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({
        left: direction === 'left' ? -100 : 100,
        behavior: 'smooth',
      });
      setTimeout(checkScroll, 300);
    }
  };

  return (
    <div className="relative flex items-center overflow-hidden h-8">
      {showArrows && canScrollLeft && (
        <button
          onClick={() => scroll('left')}
          className="absolute left-0 z-10 flex items-center justify-center cursor-pointer bg-white/80 dark:bg-[#1E1E24]/80 rounded-full"
        >
          <ChevronLeft size={12} className="text-[#8B95A1]" />
        </button>
      )}
      <div
        ref={scrollRef}
        onScroll={checkScroll}
        className="flex-1 overflow-x-auto overflow-y-hidden flex items-center"
      >
        <div className="flex items-center gap-1 flex-nowrap">
          {smsStatus.pending.map((type) => (
            <span
              key={type}
              onClick={(e) => {
                if (isEditing && onToggle) {
                  e.stopPropagation();
                  onToggle(type);
                }
              }}
              className={isEditing ? 'cursor-pointer opacity-60 hover:opacity-100 transition-opacity' : ''}
            >
              <Badge color="gray" size="xs">
                {type}
              </Badge>
            </span>
          ))}
          {smsStatus.sent.map((type) => (
            <span
              key={type}
              onClick={(e) => {
                if (isEditing && onToggle) {
                  e.stopPropagation();
                  onToggle(type);
                }
              }}
              className={isEditing ? 'cursor-pointer' : ''}
            >
              <Badge color="success" size="xs">
                {type}
              </Badge>
            </span>
          ))}
          {smsStatus.pending.length === 0 && smsStatus.sent.length === 0 && (
            <span className="text-[#B0B8C1] dark:text-[#8B95A1] text-[12px]">-</span>
          )}
        </div>
      </div>
      {showArrows && canScrollRight && (
        <button
          onClick={() => scroll('right')}
          className="absolute right-0 z-10 flex items-center justify-center cursor-pointer bg-white/80 dark:bg-[#1E1E24]/80 rounded-full"
        >
          <ChevronRight size={12} className="text-[#8B95A1]" />
        </button>
      )}
    </div>
  );
};

interface ConfirmState {
  open: boolean;
  title: string;
  content: string;
  onOk: () => void;
}

const RoomAssignment = () => {
  const navigate = useNavigate();
  const [selectedDate, setSelectedDate] = useState<Dayjs>(dayjs());
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [prevDayReservations, setPrevDayReservations] = useState<Reservation[]>([]);
  const [nextDayReservations, setNextDayReservations] = useState<Reservation[]>([]);
  const [rooms, setRooms] = useState<any[]>([]);
  const [animDirection, setAnimDirection] = useState<'none' | 'left' | 'right'>('none');
  const [loading, setLoading] = useState(false);
  const [dragOverRoom, setDragOverRoom] = useState<string | null>(null);
  const [dragOverPool, setDragOverPool] = useState(false);
  const [dragOverPartyZone, setDragOverPartyZone] = useState(false);
  const [processing, setProcessing] = useState(false);

  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formValues, setFormValues] = useState<any>({
    guest_type: 'manual',
    customer_name: '',
    phone: '',
    date: '',
    time: '18:00',
    gender: '',
    party_participants: 1,
    room_info: '',
    tags: '',
    notes: '',
    status: 'confirmed',
    source: 'manual',
  });

  const [confirmState, setConfirmState] = useState<ConfirmState>({
    open: false,
    title: '',
    content: '',
    onOk: () => {},
  });

  const showConfirm = (title: string, content: string, onOk: () => void) => {
    setConfirmState({ open: true, title, content, onOk });
  };

  const [inlineEditingId, setInlineEditingId] = useState<number | null>(null);
  const [inlineEditValues, setInlineEditValues] = useState<any>({});

  const [smsColumnWidth, setSmsColumnWidth] = useState(200);
  const [isResizing, setIsResizing] = useState(false);
  const [resizeStartX, setResizeStartX] = useState(0);
  const [resizeStartWidth, setResizeStartWidth] = useState(200);

  const GUEST_COLS = useMemo(() => {
    return `56px 120px 40px 40px 72px minmax(40px, 1fr) ${smsColumnWidth}px 50px`;
  }, [smsColumnWidth]);

  const roomInfoMap = useMemo(() => {
    const map: Record<string, string> = {};
    rooms.forEach((room) => {
      map[room.room_number] = room.room_type;
    });
    return map;
  }, [rooms]);

  const activeRoomNumbers = useMemo(() => {
    return rooms.filter((room) => room.is_active).map((room) => room.room_number);
  }, [rooms]);

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
      toast.error('객실 목록을 불러오지 못했습니다.');
    }
  }, []);

  const fetchReservations = useCallback(async (date: Dayjs) => {
    setLoading(true);
    try {
      const res = await reservationsAPI.getAll({ date: date.format('YYYY-MM-DD'), limit: 200 });
      setReservations(res.data);
    } catch {
      toast.error('예약 목록을 불러오지 못했습니다.');
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
    const fetchPreview = async (date: Dayjs, setter: (data: Reservation[]) => void) => {
      try {
        const res = await reservationsAPI.getAll({ date: date.format('YYYY-MM-DD'), limit: 200 });
        setter(res.data);
      } catch {
        setter([]);
      }
    };
    fetchPreview(selectedDate.subtract(1, 'day'), setPrevDayReservations);
    fetchPreview(selectedDate.add(1, 'day'), setNextDayReservations);
  }, [selectedDate, fetchReservations]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isResizing) {
        const delta = e.clientX - resizeStartX;
        const newWidth = Math.max(60, Math.min(400, resizeStartWidth + delta));
        setSmsColumnWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, resizeStartX, resizeStartWidth]);

  useEffect(() => {
    campaignsAPI
      .getList()
      .then((res) => {
        setCampaigns(res.data);
        if (res.data.length > 0) setSelectedCampaign(res.data[0].id);
      })
      .catch(() => {
        toast.error('캠페인 목록 로드 실패');
      });
  }, []);

  const loadTargets = async () => {
    if (!selectedCampaign) {
      toast.warning('캠페인을 선택하세요');
      return;
    }
    setTargetsLoading(true);
    try {
      const response = await campaignsAPI.preview(
        selectedCampaign,
        selectedDate.format('YYYY-MM-DD'),
      );
      setTargets(response.data.targets || []);
    } catch {
      toast.error('대상자 조회 실패');
    } finally {
      setTargetsLoading(false);
    }
  };

  const handleSendCampaign = async () => {
    if (!selectedCampaign) {
      toast.warning('캠페인을 선택하세요');
      return;
    }
    setSending(true);
    try {
      const response = await campaignsAPI.send({
        campaign_type: selectedCampaign,
        date: selectedDate.format('YYYY-MM-DD'),
      });
      toast.success(`발송 완료: ${response.data.sent_count}건 성공`);
      await loadTargets();
      await fetchReservations(selectedDate);
    } catch {
      toast.error('발송 실패');
    } finally {
      setSending(false);
    }
  };

  const handleSendRoomGuide = async () => {
    setGuideSending(true);
    try {
      const response = await campaignsAPI.sendRoomGuide({
        date: selectedDate.format('YYYY-MM-DD'),
      });
      toast.success(`객실 안내 발송 완료: ${response.data.sent_count}건`);
    } catch {
      toast.error('객실 안내 발송 실패');
    } finally {
      setGuideSending(false);
    }
  };

  const handleSendPartyGuide = async () => {
    setGuideSending(true);
    try {
      const response = await campaignsAPI.sendPartyGuide({
        date: selectedDate.format('YYYY-MM-DD'),
      });
      toast.success(`파티 안내 발송 완료: ${response.data.sent_count}건`);
    } catch {
      toast.error('파티 안내 발송 실패');
    } finally {
      setGuideSending(false);
    }
  };

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
      partyOnly: partyOnlyList,
    };
  }, [reservations]);

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
      toast.success(`${room} 배정 완료`);
      await fetchReservations(selectedDate);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || '객실 배정에 실패했습니다.');
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
      toast.success('배정 해제 완료');
      await fetchReservations(selectedDate);
    } catch {
      toast.error('배정 해제에 실패했습니다.');
    } finally {
      setProcessing(false);
    }
  };

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

    const guest = reservations.find((r) => r.id === resId);
    if (!guest) return;
    if (guest.tags?.includes('파티만')) return;

    const hasRoom = !!guest.room_number;
    showConfirm(
      '파티만으로 전환',
      hasRoom
        ? '객실 배정을 해제하고 파티만 게스트로 변경하시겠습니까?'
        : '파티만 게스트로 변경하시겠습니까?',
      async () => {
        setProcessing(true);
        try {
          if (hasRoom) {
            await reservationsAPI.assignRoom(resId, { room_number: null });
          }
          if (!guest.tags?.includes('파티만')) {
            const newTags = guest.tags ? `${guest.tags},파티만` : '파티만';
            await reservationsAPI.update(resId, { tags: newTags });
          }
          toast.success('파티만으로 전환 완료');
          await fetchReservations(selectedDate);
        } catch {
          toast.error('전환 실패');
        } finally {
          setProcessing(false);
        }
      },
    );
  };

  const handleAddPartyGuest = () => {
    setEditingId(null);
    setFormValues({
      guest_type: 'manual',
      customer_name: '',
      phone: '',
      date: selectedDate.format('YYYY-MM-DD'),
      time: '18:00',
      gender: '',
      party_participants: 1,
      room_info: '',
      tags: '',
      notes: '',
      status: 'confirmed',
      source: 'manual',
    });
    setModalVisible(true);
  };

  const handleEditGuest = (id: number) => {
    const guest = reservations.find((r) => r.id === id);
    if (guest) {
      setEditingId(id);
      setFormValues({
        ...guest,
        tags: guest.tags || '',
        guest_type: undefined,
      });
      setModalVisible(true);
    }
  };

  const handleDeleteGuest = (id: number) => {
    showConfirm('게스트 삭제', '정말 삭제하시겠습니까?', async () => {
      try {
        await reservationsAPI.delete(id);
        toast.success('삭제 완료');
        fetchReservations(selectedDate);
      } catch {
        toast.error('삭제 실패');
      }
    });
  };

  const handleSubmit = async () => {
    const values = { ...formValues };

    if (!values.customer_name) { toast.error('이름을 입력하세요'); return; }
    if (!values.phone) { toast.error('전화번호를 입력하세요'); return; }
    if (!values.date) { toast.error('날짜를 입력하세요'); return; }
    if (!values.time) { toast.error('시간을 입력하세요'); return; }

    if (!editingId && values.guest_type) {
      if (values.guest_type === 'party_only') {
        if (!values.tags?.includes('파티만')) {
          values.tags = values.tags ? `${values.tags},파티만` : '파티만';
        }
      }
      delete values.guest_type;
    }

    if (!values.room_number && !values.tags?.includes('파티만')) {
      values.tags = values.tags ? `${values.tags},파티만` : '파티만';
    }

    try {
      if (editingId) {
        await reservationsAPI.update(editingId, values);
        toast.success('수정 완료');
      } else {
        await reservationsAPI.create(values);
        toast.success('추가 완료');
      }
      setModalVisible(false);
      fetchReservations(selectedDate);
    } catch {
      toast.error('저장 실패');
    }
  };

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
      toast.success('수정 완료');
      setInlineEditingId(null);
      setInlineEditValues({});
      fetchReservations(selectedDate);
    } catch {
      toast.error('저장 실패');
    }
  };

  const handleInlineCancel = () => {
    setInlineEditingId(null);
    setInlineEditValues({});
  };

  const handleSmsToggle = async (res: Reservation, smsType: string) => {
    try {
      const currentTypes = res.sent_sms_types
        ? res.sent_sms_types.split(',').map((s) => s.trim())
        : [];

      let newTypes: string;
      if (currentTypes.includes(smsType)) {
        newTypes = currentTypes.filter((t) => t !== smsType).join(',');
        toast.success(`${smsType} 발송 미완료로 변경됨`);
      } else {
        newTypes = [...currentTypes, smsType].join(',');
        toast.success(`${smsType} 발송 완료 처리됨`);
      }

      await reservationsAPI.update(res.id, { sent_sms_types: newTypes });
      fetchReservations(selectedDate);
    } catch {
      toast.error('발송 상태 변경 실패');
    }
  };

  // Source badge
  const SourceBadge = ({ source }: { source?: string }) => {
    if (source === 'naver')
      return <Badge color="success" size="xs">네이버</Badge>;
    if (source === 'manual')
      return <Badge color="gray" size="xs">직접입력</Badge>;
    return null;
  };

  // Row drag state — returns Tailwind cursor class
  const guestAreaCursor = (
    isDragOver: boolean,
    isEditing: boolean,
    hasRes: boolean,
    variant?: 'unassigned' | 'party',
  ): string => {
    if (isDragOver || isEditing) return 'cursor-default';
    if (variant === 'unassigned' || variant === 'party') return 'cursor-grab';
    if (hasRes) return 'cursor-grab';
    return 'cursor-default';
  };

  const renderRoomRow = (room: string) => {
    const res = assignedRooms.get(room);
    const isDragOver = dragOverRoom === room;
    const isEditing = !!(res && inlineEditingId === res.id);
    const genderPeople = res
      ? [res.gender, res.party_participants].filter(Boolean).join('')
      : '';
    const party = res ? getPartyLabel(res.tags) : '';
    const smsStatus = res ? getSmsStatus(res) : { pending: [], sent: [] };

    return (
      <div
        key={room}
        className={`flex overflow-hidden select-none border-b border-[#F2F4F6] dark:border-gray-800 transition-colors
          ${isDragOver
            ? 'bg-[#E8F3FF] dark:bg-blue-900/20 ring-1 ring-inset ring-[#3182F6]/30 dark:ring-blue-700'
            : res
              ? 'bg-white dark:bg-[#1E1E24] hover:bg-[#F2F4F6] dark:hover:bg-[#2C2C34]'
              : 'bg-[#F2F4F6]/50 dark:bg-[#17171C]/30'
          }`}
        onDragOver={(e) => onRoomDragOver(e, room)}
        onDragLeave={onRoomDragLeave}
        onDrop={(e) => onRoomDrop(e, room)}
      >
        {/* Room label */}
        <div className="flex items-center gap-1.5 flex-shrink-0 pl-3 pr-2 py-2 w-36 border-r border-[#F2F4F6] dark:border-gray-800">
          <span className="font-semibold text-[#191F28] dark:text-white text-[14px]">{room}</span>
          {roomInfoMap[room] && (
            <span className="text-[12px] text-[#B0B8C1] dark:text-[#8B95A1] truncate">{roomInfoMap[room]}</span>
          )}
        </div>

        {/* Guest area */}
        <div
          draggable={!!res && !isEditing}
          onDragStart={(e) => res && !isEditing && onDragStart(e, res.id)}
          className={`flex-1 grid items-center gap-2 px-3 py-1.5 ${guestAreaCursor(isDragOver, isEditing, !!res)}`}
          style={{
            gridTemplateColumns: GUEST_COLS,
          }}
        >
          {res ? (
            isEditing ? (
              <>
                <div className="overflow-hidden">
                  <TextInput
                    sizing="sm"
                    value={inlineEditValues.customer_name}
                    onChange={(e) =>
                      setInlineEditValues({ ...inlineEditValues, customer_name: e.target.value })
                    }
                  />
                </div>
                <div className="overflow-hidden">
                  <TextInput
                    sizing="sm"
                    value={inlineEditValues.phone}
                    onChange={(e) =>
                      setInlineEditValues({ ...inlineEditValues, phone: e.target.value })
                    }
                  />
                </div>
                <div className="flex gap-1">
                  <Select
                    sizing="sm"
                    value={inlineEditValues.gender || ''}
                    onChange={(e) =>
                      setInlineEditValues({ ...inlineEditValues, gender: e.target.value })
                    }
                  >
                    <option value="">-</option>
                    <option value="남">남</option>
                    <option value="여">여</option>
                  </Select>
                  <TextInput
                    type="number"
                    sizing="sm"
                    min={1}
                    value={inlineEditValues.party_participants || ''}
                    onChange={(e) =>
                      setInlineEditValues({
                        ...inlineEditValues,
                        party_participants: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div className="text-[14px] text-[#4E5968] dark:text-gray-300 text-center">{party}</div>
                <div className="overflow-hidden">
                  <Select
                    sizing="sm"
                    value={inlineEditValues.room_info || ''}
                    onChange={(e) =>
                      setInlineEditValues({ ...inlineEditValues, room_info: e.target.value })
                    }
                  >
                    <option value="">-</option>
                    {ROOM_TYPE_OPTIONS.map((type) => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </Select>
                </div>
                <div className="overflow-hidden">
                  <TextInput
                    sizing="sm"
                    value={inlineEditValues.notes || ''}
                    onChange={(e) =>
                      setInlineEditValues({ ...inlineEditValues, notes: e.target.value })
                    }
                  />
                </div>
                <SmsCell
                  smsStatus={smsStatus}
                  isEditing={isEditing}
                  onToggle={(type) => handleSmsToggle(res, type)}
                />
                <div className="flex gap-1 justify-center">
                  <Button
                    color="light"
                    size="xs"
                    onClick={handleInlineSave}
                  >
                    <Save size={14} />
                  </Button>
                  <Button
                    color="light"
                    size="xs"
                    onClick={handleInlineCancel}
                  >
                    <XCircle size={14} />
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="overflow-hidden truncate flex items-center gap-1">
                  <span className="font-medium text-[#191F28] dark:text-white text-[14px] truncate">{res.customer_name}</span>
                  <SourceBadge source={res.source} />
                </div>
                <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400 tabular-nums">{res.phone}</div>
                <div className="text-center text-[14px] text-[#4E5968] dark:text-gray-300 font-medium">{genderPeople || <span className="text-[#B0B8C1]">-</span>}</div>
                <div className="text-center text-[14px] text-[#4E5968] dark:text-gray-300 font-medium">{party || <span className="text-[#B0B8C1]">-</span>}</div>
                <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400">{res.room_info || <span className="text-[#B0B8C1]">-</span>}</div>
                <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400">{res.notes || ''}</div>
                <SmsCell smsStatus={smsStatus} isEditing={false} />
                <div className="flex justify-center">
                  <Button
                    color="light"
                    size="xs"
                    onClick={(e) => { e.stopPropagation(); handleInlineEdit(res); }}
                  >
                    <Pencil size={14} />
                  </Button>
                </div>
              </>
            )
          ) : (
            <div className="overflow-hidden truncate col-span-full text-[14px] text-[#3182F6] dark:text-blue-400 italic">
              {isDragOver ? '여기에 놓으세요' : ''}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderUnassignedRow = (res: Reservation) => {
    const genderPeople = [res.gender, res.party_participants].filter(Boolean).join('');
    const party = getPartyLabel(res.tags);
    const smsStatus = getSmsStatus(res);
    const isEditing = inlineEditingId === res.id;

    return (
      <div
        key={res.id}
        className="flex overflow-hidden select-none border-b border-[#F2F4F6] dark:border-gray-800 bg-white dark:bg-[#1E1E24] hover:bg-[#FFF5E6]/40 dark:hover:bg-[#2C2C34] transition-colors"
        draggable={!isEditing}
        onDragStart={(e) => !isEditing && onDragStart(e, res.id)}
      >
        <div
          className={`flex-1 grid items-center gap-2 px-3 py-1.5 ${guestAreaCursor(false, isEditing, true, 'unassigned')}`}
          style={{ gridTemplateColumns: GUEST_COLS }}
        >
          <div className="overflow-hidden truncate flex items-center gap-1">
            <span className="font-medium text-[#191F28] dark:text-white text-[14px] truncate">{res.customer_name}</span>
            <SourceBadge source={res.source} />
          </div>
          <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400 tabular-nums">{res.phone}</div>
          <div className="text-center text-[14px] text-[#4E5968] dark:text-gray-300 font-medium">{genderPeople || <span className="text-[#B0B8C1]">-</span>}</div>
          <div className="text-center text-[14px] text-[#4E5968] dark:text-gray-300 font-medium">{party || <span className="text-[#B0B8C1]">-</span>}</div>
          <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400">{res.room_info || <span className="text-[#B0B8C1]">-</span>}</div>
          <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400">{res.notes || ''}</div>
          <SmsCell smsStatus={smsStatus} isEditing={false} />
          <div className="flex justify-center">
            <Button
              color="light"
              size="xs"
              onClick={(e) => { e.stopPropagation(); handleInlineEdit(res); }}
            >
              <Pencil size={14} />
            </Button>
          </div>
        </div>
      </div>
    );
  };

  const renderPartyOnlyRow = (res: Reservation, _index: number) => {
    const isEditing = inlineEditingId === res.id;
    const genderPeople = [res.gender, res.party_participants].filter(Boolean).join('');
    const party = getPartyLabel(res.tags);
    const smsStatus = getSmsStatus(res);

    return (
      <div
        key={res.id}
        className="flex overflow-hidden select-none border-b border-[#F2F4F6] dark:border-gray-800 bg-white dark:bg-[#1E1E24] hover:bg-[#F3EEFF]/40 dark:hover:bg-[#2C2C34] transition-colors"
        draggable={!isEditing}
        onDragStart={(e) => !isEditing && onDragStart(e, res.id)}
      >
        <div
          className={`flex-1 grid items-center gap-2 px-3 py-1.5 ${guestAreaCursor(false, isEditing, true, 'party')}`}
          style={{ gridTemplateColumns: GUEST_COLS }}
        >
          {isEditing ? (
            <>
              <div className="overflow-hidden">
                <TextInput
                  sizing="sm"
                  value={inlineEditValues.customer_name}
                  onChange={(e) =>
                    setInlineEditValues({ ...inlineEditValues, customer_name: e.target.value })
                  }
                />
              </div>
              <div className="overflow-hidden">
                <TextInput
                  sizing="sm"
                  value={inlineEditValues.phone}
                  onChange={(e) =>
                    setInlineEditValues({ ...inlineEditValues, phone: e.target.value })
                  }
                />
              </div>
              <div className="flex gap-1">
                <Select
                  sizing="sm"
                  value={inlineEditValues.gender || ''}
                  onChange={(e) =>
                    setInlineEditValues({ ...inlineEditValues, gender: e.target.value })
                  }
                >
                  <option value="">-</option>
                  <option value="남">남</option>
                  <option value="여">여</option>
                </Select>
                <TextInput
                  type="number"
                  sizing="sm"
                  min={1}
                  value={inlineEditValues.party_participants || ''}
                  onChange={(e) =>
                    setInlineEditValues({
                      ...inlineEditValues,
                      party_participants: Number(e.target.value),
                    })
                  }
                />
              </div>
              <div className="text-[14px] text-[#4E5968] dark:text-gray-300 text-center">{party}</div>
              <div className="overflow-hidden">
                <Select
                  sizing="sm"
                  value={inlineEditValues.room_info || ''}
                  onChange={(e) =>
                    setInlineEditValues({ ...inlineEditValues, room_info: e.target.value })
                  }
                >
                  <option value="">-</option>
                  {ROOM_TYPE_OPTIONS.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </Select>
              </div>
              <div className="overflow-hidden">
                <TextInput
                  sizing="sm"
                  value={inlineEditValues.notes || ''}
                  onChange={(e) =>
                    setInlineEditValues({ ...inlineEditValues, notes: e.target.value })
                  }
                />
              </div>
              <SmsCell
                smsStatus={smsStatus}
                isEditing={isEditing}
                onToggle={(type) => handleSmsToggle(res, type)}
              />
              <div className="flex gap-1 justify-center">
                <Button
                  color="light"
                  size="xs"
                  onClick={handleInlineSave}
                >
                  <Save size={14} />
                </Button>
                <Button
                  color="light"
                  size="xs"
                  onClick={handleInlineCancel}
                >
                  <XCircle size={14} />
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="overflow-hidden truncate flex items-center gap-1">
                <span className="font-medium text-[#191F28] dark:text-white text-[14px] truncate">{res.customer_name}</span>
                <SourceBadge source={res.source} />
              </div>
              <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400 tabular-nums">{res.phone}</div>
              <div className="text-center text-[14px] text-[#4E5968] dark:text-gray-300 font-medium">{genderPeople || <span className="text-[#B0B8C1]">-</span>}</div>
              <div className="text-center text-[14px] text-[#4E5968] dark:text-gray-300 font-medium">{party || <span className="text-[#B0B8C1]">-</span>}</div>
              <div className="overflow-hidden truncate text-[14px] text-[#7B61FF] dark:text-[#7B61FF]">파티만</div>
              <div className="overflow-hidden truncate text-[14px] text-[#8B95A1] dark:text-gray-400">{res.notes || ''}</div>
              <SmsCell smsStatus={smsStatus} isEditing={false} />
              <div className="flex gap-1 justify-center">
                <Button
                  color="light"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); handleInlineEdit(res); }}
                >
                  <Pencil size={14} />
                </Button>
                <Button
                  color="failure"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); handleDeleteGuest(res.id); }}
                >
                  <Trash2 size={14} />
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    );
  };

  const navigateDate = useCallback(
    (direction: 'prev' | 'next') => {
      if (animDirection !== 'none') return;
      const dir = direction === 'prev' ? 'left' : 'right';
      setAnimDirection(dir);
      setTimeout(() => {
        setSelectedDate((prev) =>
          direction === 'prev' ? prev.subtract(1, 'day') : prev.add(1, 'day'),
        );
        setAnimDirection('none');
      }, 350);
    },
    [animDirection],
  );

  const renderDayPreview = (
    previewReservations: Reservation[],
    date: Dayjs,
    direction: 'prev' | 'next',
  ) => {
    const roomMap = new Map<string, Reservation>();
    previewReservations.forEach((r) => {
      if (r.room_number) roomMap.set(r.room_number, r);
    });

    const isActive = animDirection === (direction === 'prev' ? 'left' : 'right');

    return (
      <div
        onClick={() => navigateDate(direction)}
        className="overflow-y-auto cursor-pointer rounded-xl border border-[#F2F4F6] dark:border-gray-800 bg-white dark:bg-[#1E1E24] px-2 py-2 w-28 flex-shrink-0 transition-all"
        style={{
          opacity: isActive ? 0.95 : 0.55,
          transform: isActive ? 'scale(1.03)' : 'scale(1)',
        }}
      >
        <div className="flex justify-between items-center px-1 mb-1.5 h-7">
          <span className="text-[12px] font-medium text-[#8B95A1] dark:text-gray-400">이름</span>
          <span className="text-[12px] font-medium text-[#8B95A1] dark:text-gray-400">성별</span>
        </div>
        <div className="text-[12px] font-semibold text-[#B0B8C1] dark:text-[#8B95A1] text-center mb-1.5">
          {date.format('M/D(ddd)')}
        </div>
        {activeRoomNumbers.map((room) => {
          const guest = roomMap.get(room);
          return (
            <div
              key={room}
              className="flex overflow-hidden select-none mb-px rounded-lg px-1 py-0.5 hover:bg-[#F2F4F6] dark:hover:bg-[#2C2C34]"
            >
              <div className="flex justify-between items-center overflow-hidden w-full">
                {guest ? (
                  <>
                    <span className="overflow-hidden truncate flex-1 text-[12px] text-[#4E5968] dark:text-gray-300">
                      {guest.customer_name}
                    </span>
                    <span className="flex-shrink-0 ml-1 text-[12px] text-[#8B95A1] dark:text-gray-400">
                      {guest.gender || '-'}
                    </span>
                  </>
                ) : (
                  <span className="text-[12px] text-[#B0B8C1] dark:text-gray-600">-</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // suppress unused navigate warning — keep for future routing
  void navigate;
  // suppress unused handleEditGuest warning — used via modal open
  void handleEditGuest;

  return (
    <div className={`space-y-4 ${processing ? 'opacity-60 pointer-events-none' : ''}`}>

      {/* Page header */}
      <div>
        <h1 className="page-title">객실 배정</h1>
        <p className="page-subtitle">날짜별 객실을 배정하고 SMS를 발송하세요</p>
      </div>

      {/* Campaign controls */}
      <div className="section-card">
        <div className="section-header">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">캠페인 발송</h2>
        </div>
        <div className="section-body py-3">
          <div className="flex flex-wrap gap-2 items-center">
            {/* Campaign chip selector */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {campaigns.map((campaign: any) => (
                <Button
                  key={campaign.id}
                  color={selectedCampaign === campaign.id ? 'blue' : 'light'}
                  size="sm"
                  onClick={() => setSelectedCampaign(campaign.id)}
                >
                  {campaign.name}
                </Button>
              ))}
              {campaigns.length === 0 && (
                <Badge color="gray" size="sm">캠페인 없음</Badge>
              )}
            </div>

            <div className="flex items-center gap-2 ml-auto">
              <Button
                color="light"
                size="sm"
                onClick={loadTargets}
                disabled={targetsLoading}
              >
                {targetsLoading ? (
                  <Spinner size="xs" className="mr-1.5" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                )}
                대상조회
              </Button>
              <Button
                color="blue"
                size="sm"
                onClick={handleSendCampaign}
                disabled={sending || targets.length === 0}
              >
                {sending ? (
                  <Spinner size="xs" className="mr-1.5" />
                ) : (
                  <Send className="h-3.5 w-3.5 mr-1.5" />
                )}
                발송 ({targets.length}건)
              </Button>

              <Button
                color="blue"
                size="sm"
                onClick={handleSendRoomGuide}
                disabled={guideSending}
              >
                <Send className="h-3.5 w-3.5 mr-1.5" />
                객실 안내
              </Button>
              <Button
                color="blue"
                size="sm"
                onClick={handleSendPartyGuide}
                disabled={guideSending}
              >
                <Send className="h-3.5 w-3.5 mr-1.5" />
                파티 안내
              </Button>
            </div>
          </div>

          {/* Target list — slide down */}
          {targets.length > 0 && (
            <div className="mt-3 rounded-lg border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3">
              <div className="flex justify-between items-center mb-2">
                <Badge color="blue" size="sm">발송 대상 {targets.length}건</Badge>
                <Button
                  color="light"
                  size="xs"
                  onClick={() => setTargets([])}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {targets.map((t: any) => (
                  <Badge key={t.id} color="gray" size="sm">
                    {t.name} {t.phone} {t.room_number || ''}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main grid card */}
      <div className="section-card">
        {/* Date navigation header */}
        <div className="section-header">
          <button
            onClick={() => navigateDate('prev')}
            className="cursor-pointer text-[14px] text-[#B0B8C1] dark:text-[#8B95A1] hover:text-[#8B95A1] dark:hover:text-gray-300 transition-colors w-24 text-center py-1 bg-transparent border-none"
          >
            {selectedDate.subtract(1, 'day').format('M/D(ddd)')}
          </button>
          <div className="flex-1 flex justify-center items-center gap-2">
            <Button
              color="light"
              size="xs"
              onClick={() => navigateDate('prev')}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <TextInput
              type="date"
              sizing="sm"
              value={selectedDate.format('YYYY-MM-DD')}
              onChange={(e) => {
                if (e.target.value) setSelectedDate(dayjs(e.target.value));
              }}
            />
            <Button
              color="light"
              size="xs"
              onClick={() => navigateDate('next')}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              color="light"
              size="sm"
              onClick={handleAddPartyGuest}
            >
              <UserPlus className="h-3.5 w-3.5 mr-1.5" />
              예약자 추가
            </Button>
          </div>
          <button
            onClick={() => navigateDate('next')}
            className="cursor-pointer text-[14px] text-[#B0B8C1] dark:text-[#8B95A1] hover:text-[#8B95A1] dark:hover:text-gray-300 transition-colors w-24 text-center py-1 bg-transparent border-none"
          >
            {selectedDate.add(1, 'day').format('M/D(ddd)')}
          </button>
        </div>

        <div className="section-body">
          <div className="flex gap-3">
            {renderDayPreview(prevDayReservations, selectedDate.subtract(1, 'day'), 'prev')}

            <div className="flex-1 overflow-hidden">
              <div
                className={
                  animDirection === 'left'
                    ? 'cylinder-rotate-left'
                    : animDirection === 'right'
                      ? 'cylinder-rotate-right'
                      : ''
                }
              >
                {/* Unified Table */}
                <div className="overflow-x-auto rounded-xl border border-[#F2F4F6] dark:border-gray-800">
                  {/* Header */}
                  <div className="flex items-center h-9 bg-[#F2F4F6] dark:bg-[#17171C] border-b border-[#F2F4F6] dark:border-gray-800">
                    <div className="flex-shrink-0 pl-3 pr-2 w-36 border-r border-[#F2F4F6] dark:border-gray-800">
                      <span className="text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">객실</span>
                    </div>
                    <div
                      className="flex-1 grid gap-2 pl-3"
                      style={{ gridTemplateColumns: GUEST_COLS }}
                    >
                      <div className="text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">이름</div>
                      <div className="text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">전화번호</div>
                      <div className="text-center text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">성별</div>
                      <div className="text-center text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">파티</div>
                      <div className="text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">예약객실</div>
                      <div className="text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">메모</div>
                      <div className="relative flex items-center text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">
                        문자
                        <div
                          id="sms-column-resizer"
                          className="absolute cursor-col-resize z-10 w-2 -right-1 -top-1.5 -bottom-1.5 hover:bg-[#3182F6]/30"
                          onMouseDown={(e) => {
                            setIsResizing(true);
                            setResizeStartX(e.clientX);
                            setResizeStartWidth(smsColumnWidth);
                          }}
                        />
                      </div>
                      <div className="text-[12px] font-semibold uppercase tracking-wide text-[#8B95A1] dark:text-gray-400">작업</div>
                    </div>
                  </div>

                  {/* Loading */}
                  {loading && (
                    <div className="flex items-center justify-center gap-2 py-12 text-[#B0B8C1] dark:text-[#8B95A1]">
                      <Spinner size="sm" />
                      <span className="text-sm">로딩 중...</span>
                    </div>
                  )}

                  {/* Room Rows */}
                  {!loading && activeRoomNumbers.map(renderRoomRow)}

                  {/* Unassigned Pool */}
                  <div
                    className={`mt-0 border-t-2 transition-colors ${
                      dragOverPool
                        ? 'border-[#FF9F00] bg-[#FFF5E6] dark:bg-amber-900/20'
                        : 'border-[#F2F4F6] dark:border-gray-800'
                    }`}
                    onDragOver={onPoolDragOver}
                    onDragLeave={onPoolDragLeave}
                    onDrop={onPoolDrop}
                  >
                    {unassigned.length === 0 && !loading ? (
                      <div className="flex items-center gap-2 py-3 px-4">
                        <div className="flex-shrink-0 w-36 flex items-center">
                          <Badge color="warning" size="sm">미배정</Badge>
                        </div>
                        <p className="text-[14px] text-[#B0B8C1] dark:text-[#8B95A1] italic">미배정 예약이 없습니다</p>
                      </div>
                    ) : (
                      <div className="flex">
                        <div className="flex-shrink-0 flex items-center justify-start pl-3 w-36 border-r border-[#F2F4F6] dark:border-gray-800 py-2">
                          <Badge color="warning" size="sm">미배정</Badge>
                        </div>
                        <div className="flex-1">
                          {unassigned.map((res) => renderUnassignedRow(res))}
                        </div>
                      </div>
                    )}
                    {dragOverPool && (
                      <div className="text-center py-2 text-[14px] text-[#FF9F00] dark:text-[#FF9F00] font-medium">
                        여기에 놓으면 배정 해제
                      </div>
                    )}
                  </div>

                  {/* Party-Only */}
                  <div
                    className={`border-t-2 transition-colors ${
                      dragOverPartyZone
                        ? 'border-[#7B61FF] bg-[#F3EEFF] dark:bg-purple-900/20'
                        : 'border-[#F2F4F6] dark:border-gray-800'
                    }`}
                    onDragOver={onPartyZoneDragOver}
                    onDragLeave={onPartyZoneDragLeave}
                    onDrop={onPartyZoneDrop}
                  >
                    {partyOnly.length === 0 ? (
                      <div className="flex items-center gap-2 py-3 px-4">
                        <div className="flex-shrink-0 w-36 flex items-center">
                          <Badge color="purple" size="sm">파티만</Badge>
                        </div>
                        <p className="text-[14px] text-[#B0B8C1] dark:text-[#8B95A1] italic">
                          {dragOverPartyZone
                            ? '여기에 놓으면 파티만 게스트로 전환됩니다'
                            : '파티만 게스트가 없습니다'}
                        </p>
                      </div>
                    ) : (
                      <div className="flex">
                        <div className="flex-shrink-0 flex items-center justify-start pl-3 w-36 border-r border-[#F2F4F6] dark:border-gray-800 py-2">
                          <Badge color="purple" size="sm">파티만</Badge>
                        </div>
                        <div className="flex-1">
                          {partyOnly.map((res, idx) => renderPartyOnlyRow(res, idx))}
                        </div>
                      </div>
                    )}
                    {dragOverPartyZone && partyOnly.length > 0 && (
                      <div className="text-center py-2 text-[14px] text-[#7B61FF] dark:text-[#7B61FF] font-medium">
                        여기에 놓으면 파티만 게스트로 전환됩니다
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {renderDayPreview(nextDayReservations, selectedDate.add(1, 'day'), 'next')}
          </div>
        </div>
      </div>

      {/* Guest Form Modal */}
      <Modal show={modalVisible} onClose={() => setModalVisible(false)} size="lg">
        <ModalHeader>{editingId ? '게스트 수정' : '예약자 추가'}</ModalHeader>
        <ModalBody>
          <div className="flex flex-col gap-4">
            {!editingId && (
              <div className="space-y-2">
                <Label htmlFor="guest-type">예약자 타입</Label>
                <Select
                  id="guest-type"
                  value={formValues.guest_type || 'manual'}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === 'party_only') {
                      const currentTags = formValues.tags;
                      if (!currentTags || !currentTags.includes('파티만')) {
                        setFormValues({ ...formValues, guest_type: val, tags: '파티만' });
                        return;
                      }
                    }
                    setFormValues({ ...formValues, guest_type: val });
                  }}
                >
                  <option value="manual">직접 입력 — 수동으로 추가된 예약자</option>
                  <option value="party_only">파티만 — 객실 없이 파티만 참석</option>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="customer-name">이름 <span className="text-[#F04452]">*</span></Label>
              <TextInput
                id="customer-name"
                value={formValues.customer_name || ''}
                onChange={(e) => setFormValues({ ...formValues, customer_name: e.target.value })}
                placeholder="이름"
                sizing="sm"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">전화번호 <span className="text-[#F04452]">*</span></Label>
              <TextInput
                id="phone"
                value={formValues.phone || ''}
                onChange={(e) => setFormValues({ ...formValues, phone: e.target.value })}
                placeholder="010-1234-5678"
                sizing="sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="date">날짜 <span className="text-[#F04452]">*</span></Label>
                <TextInput
                  id="date"
                  type="date"
                  value={formValues.date || ''}
                  onChange={(e) => setFormValues({ ...formValues, date: e.target.value })}
                  sizing="sm"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="time">시간 <span className="text-[#F04452]">*</span></Label>
                <TextInput
                  id="time"
                  type="time"
                  value={formValues.time || ''}
                  onChange={(e) => setFormValues({ ...formValues, time: e.target.value })}
                  sizing="sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="gender">성별</Label>
                <Select
                  id="gender"
                  value={formValues.gender || ''}
                  onChange={(e) => setFormValues({ ...formValues, gender: e.target.value })}
                >
                  <option value="">성별 선택</option>
                  <option value="남">남</option>
                  <option value="여">여</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="party-participants">참여 인원</Label>
                <TextInput
                  id="party-participants"
                  type="number"
                  min={1}
                  value={formValues.party_participants || 1}
                  onChange={(e) =>
                    setFormValues({ ...formValues, party_participants: Number(e.target.value) })
                  }
                  sizing="sm"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="room-info">예약 객실</Label>
              <Select
                id="room-info"
                value={formValues.room_info || ''}
                onChange={(e) => setFormValues({ ...formValues, room_info: e.target.value })}
              >
                <option value="">예약 객실 타입 선택</option>
                {ROOM_TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </Select>
            </div>

            <div className="space-y-2">
              <Label>태그</Label>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {TAG_OPTIONS.map((tag) => {
                  const currentTags = (formValues.tags || '')
                    .split(',')
                    .map((t: string) => t.trim())
                    .filter(Boolean);
                  const active = currentTags.includes(tag);
                  return (
                    <Button
                      key={tag}
                      type="button"
                      color={active ? 'blue' : 'light'}
                      size="xs"
                      onClick={() => {
                        const tags = (formValues.tags || '')
                          .split(',')
                          .map((t: string) => t.trim())
                          .filter(Boolean);
                        const newTags = active
                          ? tags.filter((t: string) => t !== tag)
                          : [...tags, tag];
                        setFormValues({ ...formValues, tags: newTags.join(',') });
                      }}
                    >
                      {tag}
                    </Button>
                  );
                })}
              </div>
              <TextInput
                value={formValues.tags || ''}
                onChange={(e) => setFormValues({ ...formValues, tags: e.target.value })}
                placeholder="태그 (쉼표로 구분, 예: 1초,2차만)"
                sizing="sm"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">메모</Label>
              <textarea
                id="notes"
                className="w-full rounded-xl border border-[#F2F4F6] bg-[#F2F4F6] px-3 py-2 text-[14px] text-[#191F28] placeholder-[#B0B8C1] focus:border-[#3182F6] focus:ring-[#3182F6] dark:border-gray-800 dark:bg-[#1E1E24] dark:text-white dark:placeholder-gray-400"
                value={formValues.notes || ''}
                onChange={(e) => setFormValues({ ...formValues, notes: e.target.value })}
                placeholder="추가 정보나 요청사항"
                rows={3}
              />
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button color="blue" onClick={handleSubmit}>저장</Button>
          <Button color="light" onClick={() => setModalVisible(false)}>취소</Button>
        </ModalFooter>
      </Modal>

      {/* Confirm Dialog */}
      <Modal
        show={confirmState.open}
        onClose={() => setConfirmState((s) => ({ ...s, open: false }))}
        size="sm"
      >
        <ModalBody>
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-50 dark:bg-amber-900/20">
              <Trash2 className="h-6 w-6 text-amber-500" />
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">{confirmState.title}</h3>
            <p className="mb-5 text-sm text-gray-500 dark:text-gray-400">{confirmState.content}</p>
            <div className="flex justify-center gap-3">
              <Button
                color="blue"
                onClick={() => {
                  setConfirmState((s) => ({ ...s, open: false }));
                  confirmState.onOk();
                }}
              >
                확인
              </Button>
              <Button
                color="light"
                onClick={() => setConfirmState((s) => ({ ...s, open: false }))}
              >
                취소
              </Button>
            </div>
          </div>
        </ModalBody>
      </Modal>

      {/* Animations */}
      <style>{`
        @keyframes slideLeft {
          0%   { transform: translateX(0);    opacity: 1;   }
          45%  { transform: translateX(-60px); opacity: 0.2; }
          55%  { transform: translateX(40px);  opacity: 0.2; }
          100% { transform: translateX(0);    opacity: 1;   }
        }
        @keyframes slideRight {
          0%   { transform: translateX(0);   opacity: 1;   }
          45%  { transform: translateX(60px); opacity: 0.2; }
          55%  { transform: translateX(-40px);opacity: 0.2; }
          100% { transform: translateX(0);   opacity: 1;   }
        }
        .cylinder-rotate-left  { animation: slideLeft  0.35s ease-in-out; }
        .cylinder-rotate-right { animation: slideRight 0.35s ease-in-out; }
      `}</style>
    </div>
  );
};

export default RoomAssignment;
