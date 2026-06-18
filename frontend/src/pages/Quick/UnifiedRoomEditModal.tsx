import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';

import { roomsAPI } from '@/services/api';
import { queryKeys } from '@/lib/queryKeys';

import { Modal, ModalHeader, ModalBody, ModalFooter } from '@/components/ui/modal';
import { TextInput } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

// ── Types (RoomSettings.tsx vocabulary 미러) ──────────────

interface BizItemLinkDetail {
  biz_item_id: string;
  male_priority: number;
  female_priority: number;
}

interface Room {
  id: number;
  room_number: string;
  room_type: string;
  active: boolean;
  sort_order: number;
  naver_biz_item_id?: string | null;
  biz_item_ids?: string[];
  biz_item_links_detail?: BizItemLinkDetail[];
  room_memo?: string | null;
  grade?: number | null;
}

interface NaverBizItem {
  id: number;
  biz_item_id: string;
  name: string;
  exposed?: boolean;
  active: boolean;
}

interface Props {
  show: boolean;
  roomId: number | null;
  onClose: () => void;
  onSaved?: () => void;
}

// ── 상수 ──────────────────────────────────────────────────

const GRADE_OPTIONS = [1, 2, 3, 4, 5];
const GRADE_LABELS: Record<number, string> = {
  1: '도미',
  2: '더블',
  3: '트윈',
  4: '트윈3인실',
  5: '스위트',
};
const GRADE_GUIDE_TEXT = '1=도미 < 2=더블 < 3=트윈 < 4=트윈3인실 < 5=스위트';

const STEP_LABELS = ['연결 상품', '객실 타입', '객실 등급', '객실 순서', '객실 메모'];
const TOTAL_STEPS = STEP_LABELS.length;

type Priorities = Record<string, { male_priority: number; female_priority: number }>;

// 테넌트 그룹핑 규약 — res_id 단독 노출 금지.
function formatAffected(ids: number[]): string {
  const tenantId = localStorage.getItem('sms-tenant-id') || '?';
  return `[tid=${tenantId}] res=${ids.join(', ')}`;
}

// ── Component ─────────────────────────────────────────────

export default function UnifiedRoomEditModal({ show, roomId, onClose, onSaved }: Props) {
  const qc = useQueryClient();

  // 데이터 (모달 오픈 시 1회 fetch).
  const [allRooms, setAllRooms] = useState<Room[]>([]);
  const [bizItems, setBizItems] = useState<NaverBizItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 위저드.
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  // 편집 상태.
  const [roomNumber, setRoomNumber] = useState(''); // 비편집 — prefill 보존·전송용.
  const [selectedBizIds, setSelectedBizIds] = useState<string[]>([]);
  const [priorities, setPriorities] = useState<Priorities>({});
  const [roomType, setRoomType] = useState('');
  const [grade, setGrade] = useState<number | ''>('');
  const [orderedRoomIds, setOrderedRoomIds] = useState<number[]>([]);
  const [roomMemo, setRoomMemo] = useState('');

  // 오픈 시 스냅샷 (dirty diff 기준).
  const [snapshot, setSnapshot] = useState<{
    links: string;
    roomType: string;
    grade: number | '';
    order: string;
    roomMemo: string;
  } | null>(null);

  const currentRoom = useMemo(() => allRooms.find((r) => r.id === roomId) ?? null, [allRooms, roomId]);

  // ── 데이터 로드 + prefill ──
  useEffect(() => {
    if (!show || roomId == null) return;
    let alive = true;
    setLoading(true);
    setStep(1);
    Promise.all([
      roomsAPI.getAll({ include_inactive: true }).then((r) => r.data as Room[]),
      roomsAPI.getBizItems().then((r) => r.data as NaverBizItem[]),
    ])
      .then(([roomList, bizList]) => {
        if (!alive) return;
        setAllRooms(roomList);
        setBizItems(bizList);
        const room = roomList.find((r) => r.id === roomId);
        if (!room) {
          toast.error('객실을 찾을 수 없습니다.');
          return;
        }
        prefill(room, roomList);
      })
      .catch(() => {
        if (alive) toast.error('객실 정보를 불러오지 못했습니다.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show, roomId]);

  function prefill(room: Room, roomList: Room[]) {
    const ids = room.biz_item_ids && room.biz_item_ids.length > 0
      ? room.biz_item_ids
      : room.naver_biz_item_id
        ? [room.naver_biz_item_id]
        : [];

    const prio: Priorities = {};
    for (const link of room.biz_item_links_detail ?? []) {
      prio[link.biz_item_id] = { male_priority: link.male_priority, female_priority: link.female_priority };
    }
    for (const id of ids) {
      if (!prio[id]) prio[id] = { male_priority: 0, female_priority: 0 };
    }

    const g: number | '' = typeof room.grade === 'number' ? room.grade : '';

    // 스텝4: 전체 객실(비활성·미노출 포함)을 sort_order 순으로.
    // reorder 백엔드는 테넌트 전체 객실 id 와 정확히 일치해야 함(부분 전송=400) — RoomSettings 와 동일하게 full set 사용.
    const fullOrder = [...roomList]
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((r) => r.id);

    setRoomNumber(room.room_number);
    setSelectedBizIds(ids);
    setPriorities(prio);
    setRoomType(room.room_type);
    setGrade(g);
    setOrderedRoomIds(fullOrder);
    setRoomMemo(room.room_memo || '');

    setSnapshot({
      links: serializeLinks(ids, prio),
      roomType: room.room_type,
      grade: g,
      order: fullOrder.join(','),
      roomMemo: room.room_memo || '',
    });
  }

  function serializeLinks(ids: string[], prio: Priorities): string {
    const sorted = [...ids].sort();
    return JSON.stringify(
      sorted.map((id) => ({
        biz_item_id: id,
        male_priority: prio[id]?.male_priority ?? 0,
        female_priority: prio[id]?.female_priority ?? 0,
      })),
    );
  }

  // ── 스텝 1: biz_item 토글칩 (RoomSettings idiom 미러) ──
  const toggleBizItem = (bizItemId: string) => {
    setSelectedBizIds((prev) => {
      const already = prev.includes(bizItemId);
      const next = already ? prev.filter((id) => id !== bizItemId) : [...prev, bizItemId];
      setPriorities((p) => {
        const np = { ...p };
        if (already) delete np[bizItemId];
        else if (!np[bizItemId]) np[bizItemId] = { male_priority: 0, female_priority: 0 };
        return np;
      });
      return next;
    });
  };

  // ── 스텝 4: ▲▼ 이동 ──
  const moveRoom = (direction: -1 | 1) => {
    if (roomId == null) return;
    setOrderedRoomIds((prev) => {
      const idx = prev.indexOf(roomId);
      const target = idx + direction;
      if (idx === -1 || target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  };

  // ── 저장: 마지막 스텝에서 한 번에 (per-call try/catch) ──
  const handleSave = async () => {
    if (roomId == null || !snapshot) return;

    if (!roomNumber.trim() || !roomType.trim()) {
      toast.error('객실 번호와 타입은 필수입니다.');
      return;
    }

    const linksDirty = serializeLinks(selectedBizIds, priorities) !== snapshot.links;
    const roomTypeDirty = roomType !== snapshot.roomType;
    const memoDirty = roomMemo !== snapshot.roomMemo;
    const call1Dirty = linksDirty || roomTypeDirty || memoDirty;

    const gradeDirty = grade !== snapshot.grade && grade !== '';
    const orderDirty = orderedRoomIds.join(',') !== snapshot.order;

    if (!call1Dirty && !gradeDirty && !orderDirty) {
      toast.info('변경된 내용이 없습니다.');
      return;
    }

    setSaving(true);
    let hadFailure = false;

    // Call 1 — PUT /api/rooms/{id} (스텝1·2·5 중 하나라도 dirty).
    if (call1Dirty) {
      try {
        const res = await roomsAPI.update(roomId, {
          room_number: roomNumber,
          room_type: roomType,
          room_memo: roomMemo || null,
          biz_item_links: selectedBizIds.map((id) => ({
            biz_item_id: id,
            male_priority: priorities[id]?.male_priority ?? 0,
            female_priority: priorities[id]?.female_priority ?? 0,
          })),
        });
        const warning: string | undefined = res?.data?.warning;
        const ids: number[] = res?.data?.affected_reservation_ids ?? [];
        if (warning) {
          toast.warning(ids.length > 0 ? `${warning} · ${formatAffected(ids)}` : warning);
        }
      } catch (e: any) {
        hadFailure = true;
        toast.error(`객실/상품 저장 실패: ${e?.response?.data?.detail || '오류'}`);
      }
    }

    // Call 2 — PATCH /api/rooms/grades (스텝3 dirty).
    if (gradeDirty) {
      try {
        await roomsAPI.updateRoomGrades([{ id: roomId, grade: Number(grade) }]);
      } catch (e: any) {
        hadFailure = true;
        toast.error(`객실 등급 저장 실패: ${e?.response?.data?.detail || '오류'}`);
      }
    }

    // Call 3 — POST /api/rooms/reorder (스텝4 dirty, 전체 순서).
    if (orderDirty) {
      try {
        await roomsAPI.reorder(orderedRoomIds);
      } catch (e: any) {
        hadFailure = true;
        toast.error(`객실 순서 저장 실패: ${e?.response?.data?.detail || '오류'}`);
      }
    }

    qc.invalidateQueries({ queryKey: queryKeys.rooms.all() });
    qc.invalidateQueries({ queryKey: queryKeys.reservations.all() });

    setSaving(false);

    if (hadFailure) {
      return; // 모달 유지.
    }

    toast.success('저장 완료');
    onSaved?.();
    onClose();
  };

  if (!show) return null;

  const isFirst = step === 1;
  const isLast = step === TOTAL_STEPS;

  return (
    <Modal show={show} onClose={onClose} size="lg">
      <ModalHeader>
        객실 편집{currentRoom ? ` · ${currentRoom.room_number}` : ''}
      </ModalHeader>
      <ModalBody>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* 진행 표시 */}
            <div className="flex items-center justify-between">
              <span className="text-subheading font-semibold text-[#191F28] dark:text-white">
                스텝 {step} / {TOTAL_STEPS} · {STEP_LABELS[step - 1]}
              </span>
              <div className="flex gap-1.5">
                {STEP_LABELS.map((_, i) => (
                  <span
                    key={i}
                    className={`h-1.5 w-6 rounded-full ${
                      i + 1 === step
                        ? 'bg-[#3182F6]'
                        : i + 1 < step
                          ? 'bg-[#3182F6]/40'
                          : 'bg-[#E5E8EB] dark:bg-gray-700'
                    }`}
                  />
                ))}
              </div>
            </div>

            <div className="section-card">
              <div className="flex flex-col gap-4 p-4">
                {/* 스텝 1 · 연결 상품 */}
                {step === 1 && (
                  <div className="space-y-2">
                    <Label>연결 상품</Label>
                    {bizItems.length === 0 ? (
                      <p className="text-caption text-[#B0B8C1]">상품 없음 (상품 동기화 후 사용)</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {bizItems.map((item) => {
                          const selected = selectedBizIds.includes(item.biz_item_id);
                          return (
                            <button
                              key={item.biz_item_id}
                              type="button"
                              onClick={() => toggleBizItem(item.biz_item_id)}
                              className={`rounded-lg px-3 py-1.5 text-body transition-colors ${
                                selected
                                  ? 'bg-[#3182F6] text-white dark:bg-[#3182F6]'
                                  : 'bg-[#F2F4F6] text-[#8B95A1] hover:bg-[#E5E8EB] dark:bg-[#2C2C34] dark:text-gray-400 dark:hover:bg-[#35353E]'
                              }`}
                            >
                              {item.exposed === false ? `[미노출] ${item.name}` : item.name}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {selectedBizIds.length > 0 && (
                      <p className="pt-1 text-caption text-[#3182F6]">{selectedBizIds.length}개 선택됨</p>
                    )}
                    <p className="text-caption text-[#8B95A1] dark:text-gray-500">
                      ℹ 해제한 칩의 링크는 삭제됩니다 (전체 집합 전송).
                    </p>
                  </div>
                )}

                {/* 스텝 2 · 객실 타입 */}
                {step === 2 && (
                  <div className="space-y-2">
                    <Label htmlFor="q-room-type">
                      객실 타입 <span className="text-[#F04452]">*</span>
                    </Label>
                    <TextInput
                      id="q-room-type"
                      value={roomType}
                      onChange={(e) => setRoomType(e.target.value)}
                      placeholder="트윈룸"
                    />
                  </div>
                )}

                {/* 스텝 3 · 객실 등급 */}
                {step === 3 && (
                  <div className="space-y-2">
                    <Label htmlFor="q-grade">객실 등급</Label>
                    <Select
                      id="q-grade"
                      value={grade}
                      onChange={(e) => setGrade(e.target.value ? parseInt(e.target.value) : '')}
                    >
                      <option value="">미설정</option>
                      {GRADE_OPTIONS.map((g) => (
                        <option key={g} value={g}>
                          {g} · {GRADE_LABELS[g]}
                        </option>
                      ))}
                    </Select>
                    <p className="text-caption text-[#8B95A1] dark:text-gray-500">{GRADE_GUIDE_TEXT}</p>
                  </div>
                )}

                {/* 스텝 4 · 객실 순서 */}
                {step === 4 && (
                  <div className="space-y-2">
                    <Label>객실 순서</Label>
                    <p className="text-caption text-[#8B95A1] dark:text-gray-500">
                      ▲▼ 로 이 객실의 위치를 옮기세요.
                    </p>
                    <div className="flex max-h-72 flex-col gap-1 overflow-y-auto">
                      {orderedRoomIds.map((id, idx) => {
                        const r = allRooms.find((rm) => rm.id === id);
                        const isTarget = id === roomId;
                        return (
                          <div
                            key={id}
                            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 ${
                              isTarget
                                ? 'bg-[#E8F3FF] dark:bg-[#3182F6]/15'
                                : 'bg-[#F8F9FA] dark:bg-[#1E1E24]'
                            }`}
                          >
                            <span className="w-6 shrink-0 text-caption tabular-nums text-[#8B95A1] dark:text-gray-500">
                              {idx + 1}
                            </span>
                            <span
                              className={`flex-1 truncate text-body ${
                                isTarget
                                  ? 'font-semibold text-[#3182F6]'
                                  : 'text-[#4E5968] dark:text-gray-300'
                              }`}
                            >
                              {r ? `${r.room_number} · ${r.room_type}` : `#${id}`}
                            </span>
                            {isTarget && (
                              <div className="flex shrink-0 gap-1">
                                <Button
                                  color="light"
                                  size="xs"
                                  onClick={() => moveRoom(-1)}
                                  disabled={idx === 0}
                                  aria-label="위로"
                                >
                                  <ChevronUp className="h-3.5 w-3.5" />
                                </Button>
                                <Button
                                  color="light"
                                  size="xs"
                                  onClick={() => moveRoom(1)}
                                  disabled={idx === orderedRoomIds.length - 1}
                                  aria-label="아래로"
                                >
                                  <ChevronDown className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 스텝 5 · 객실 메모 */}
                {step === 5 && (
                  <div className="space-y-2">
                    <Label htmlFor="q-memo">객실 메모</Label>
                    <TextInput
                      id="q-memo"
                      value={roomMemo}
                      onChange={(e) => setRoomMemo(e.target.value)}
                      placeholder="더블→트윈 전환 등"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </ModalBody>
      <ModalFooter className="justify-between">
        <Button color="light" onClick={onClose} disabled={saving}>
          취소
        </Button>
        <div className="flex items-center gap-2">
          <Button color="light" onClick={() => setStep((s) => Math.max(1, s - 1))} disabled={isFirst || saving}>
            이전
          </Button>
          {isLast ? (
            <Button color="blue" onClick={handleSave} disabled={saving || loading}>
              {saving ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  저장 중...
                </>
              ) : (
                '저장'
              )}
            </Button>
          ) : (
            <Button color="blue" onClick={() => setStep((s) => Math.min(TOTAL_STEPS, s + 1))} disabled={loading}>
              다음
            </Button>
          )}
        </div>
      </ModalFooter>
    </Modal>
  );
}
