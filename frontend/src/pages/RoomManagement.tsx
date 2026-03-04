import { useEffect, useState, DragEvent } from 'react';
import { Home, Plus, Pencil, Trash2, GripVertical } from 'lucide-react';
import { toast } from 'sonner';
import { roomsAPI } from '@/services/api';

import {
  Button,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  TextInput,
  Label,
  ToggleSwitch,
  Badge,
  Spinner,
} from 'flowbite-react';

interface Room {
  id: number;
  room_number: string;
  room_type: string;
  is_active: boolean;
  sort_order: number;
  created_at: string;
}

interface RoomForm {
  room_number: string;
  room_type: string;
  sort_order: number;
  is_active: boolean;
}

const EMPTY_FORM: RoomForm = {
  room_number: '',
  room_type: '',
  sort_order: 1,
  is_active: true,
};

const RoomManagement = () => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<RoomForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<Room | null>(null);

  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  useEffect(() => {
    loadRooms();
  }, []);

  const loadRooms = async () => {
    setLoading(true);
    try {
      const res = await roomsAPI.getAll({ include_inactive: true });
      setRooms(res.data);
    } catch {
      toast.error('객실 목록 로드 실패');
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, sort_order: rooms.length + 1 });
    setDialogOpen(true);
  };

  const openEdit = (room: Room) => {
    setEditingId(room.id);
    setForm({
      room_number: room.room_number,
      room_type: room.room_type,
      sort_order: room.sort_order,
      is_active: room.is_active,
    });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.room_number.trim() || !form.room_type.trim()) {
      toast.error('객실 번호와 타입은 필수입니다');
      return;
    }
    setSaving(true);
    try {
      if (editingId !== null) {
        await roomsAPI.update(editingId, form);
        toast.success('수정 완료');
      } else {
        await roomsAPI.create(form);
        toast.success('추가 완료');
      }
      setDialogOpen(false);
      loadRooms();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await roomsAPI.delete(deleteTarget.id);
      toast.success('삭제 완료');
      loadRooms();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || '삭제 실패');
    } finally {
      setDeleteTarget(null);
    }
  };

  // ── Drag and Drop ────────────────────────────────────

  const onDragStart = (e: DragEvent, index: number) => {
    e.dataTransfer.setData('text/plain', String(index));
    e.dataTransfer.effectAllowed = 'move';
    setDraggingIndex(index);
  };

  const onDragEnd = () => {
    setDraggingIndex(null);
    setDragOverIndex(null);
  };

  const onDropZoneDragOver = (e: DragEvent, insertIndex: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(insertIndex);
  };

  const onDropZoneDragLeave = () => {
    setDragOverIndex(null);
  };

  const onDropZoneDrop = async (e: DragEvent, insertIndex: number) => {
    e.preventDefault();
    setDragOverIndex(null);
    setDraggingIndex(null);

    const sourceIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
    let targetIndex = insertIndex;
    if (sourceIndex < insertIndex) targetIndex = insertIndex - 1;
    if (sourceIndex === targetIndex) return;

    const newRooms = [...rooms];
    const [moved] = newRooms.splice(sourceIndex, 1);
    newRooms.splice(targetIndex, 0, moved);

    setRooms(newRooms);

    try {
      await Promise.all(
        newRooms.map((room, idx) => roomsAPI.update(room.id, { sort_order: idx + 1 }))
      );
      toast.success('정렬 순서 변경 완료');
      loadRooms();
    } catch {
      toast.error('정렬 순서 변경 실패');
      loadRooms();
    }
  };

  // ── Render ───────────────────────────────────────────

  const renderDropZone = (insertIndex: number) => {
    const isActive =
      dragOverIndex === insertIndex &&
      draggingIndex !== null &&
      draggingIndex !== insertIndex &&
      draggingIndex !== insertIndex - 1;

    return (
      <div
        key={`drop-${insertIndex}`}
        onDragOver={(e) => onDropZoneDragOver(e, insertIndex)}
        onDragLeave={onDropZoneDragLeave}
        onDrop={(e) => onDropZoneDrop(e, insertIndex)}
        className={`h-1 rounded-full transition-all ${
          isActive ? 'my-1 h-2 bg-[#3182F6]' : 'bg-transparent'
        }`}
      />
    );
  };

  const renderRoomCard = (room: Room, index: number) => {
    const isDragging = draggingIndex === index;

    return (
      <div
        key={room.id}
        draggable
        onDragStart={(e) => onDragStart(e, index)}
        onDragEnd={onDragEnd}
        className={`transition-opacity ${isDragging ? 'cursor-grabbing opacity-40' : 'cursor-grab'}`}
      >
        <div className="flex items-center gap-3 rounded-xl bg-[#F2F4F6] px-4 py-3 transition-colors hover:bg-[#E5E8EB] dark:bg-[#1E1E24] dark:hover:bg-[#2C2C34]">
          <GripVertical size={16} className="drag-handle shrink-0" />
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white text-[12px] font-semibold tabular-nums text-[#4E5968] dark:bg-[#2C2C34] dark:text-gray-300">
            {index + 1}
          </span>
          <span className="font-semibold text-[#191F28] dark:text-white">{room.room_number}</span>
          <Badge color="gray">{room.room_type}</Badge>
          {room.is_active ? (
            <Badge color="success">활성</Badge>
          ) : (
            <Badge color="gray">비활성</Badge>
          )}
          <span className="ml-auto hidden text-[12px] text-[#B0B8C1] sm:inline">
            {new Date(room.created_at).toLocaleString('ko-KR')}
          </span>
          <div className="flex items-center gap-1">
            <Button
              color="light"
              size="xs"
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); openEdit(room); }}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              color="light"
              size="xs"
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); setDeleteTarget(room); }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2.5">
          <div className="stat-icon bg-[#E8F3FF] text-[#3182F6] dark:bg-[#3182F6]/15 dark:text-[#3182F6]">
            <Home size={20} />
          </div>
          <div>
            <h1 className="page-title">객실 설정</h1>
            <p className="page-subtitle">객실을 추가, 수정, 삭제하고 순서를 변경합니다.</p>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-header">
          <Button color="blue" size="sm" onClick={openCreate}>
            <Plus className="mr-1.5 h-4 w-4" />
            객실 추가
          </Button>
          <div className="flex items-center gap-1.5 text-[12px] text-[#B0B8C1]">
            <GripVertical size={14} />
            <span>드래그하여 순서 변경</span>
          </div>
        </div>

        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Spinner size="lg" />
            </div>
          ) : rooms.length === 0 ? (
            <div className="empty-state">
              <Home size={40} strokeWidth={1} />
              <p className="text-[14px]">등록된 객실이 없습니다</p>
            </div>
          ) : (
            <div className="space-y-1">
              {rooms.map((room, index) => (
                <div key={room.id}>
                  {renderDropZone(index)}
                  {renderRoomCard(room, index)}
                </div>
              ))}
              {renderDropZone(rooms.length)}
            </div>
          )}
        </div>
      </div>

      {/* Room Modal */}
      <Modal show={dialogOpen} onClose={() => setDialogOpen(false)} size="md">
        <ModalHeader>{editingId !== null ? '객실 수정' : '객실 추가'}</ModalHeader>
        <ModalBody>
          <div className="flex flex-col gap-5">
            <div className="space-y-2">
              <Label htmlFor="room-number">객실 번호 <span className="text-[#F04452]">*</span></Label>
              <TextInput
                id="room-number"
                value={form.room_number}
                onChange={(e) => setForm((f) => ({ ...f, room_number: e.target.value }))}
                placeholder="A101"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="room-type">객실 타입 <span className="text-[#F04452]">*</span></Label>
              <TextInput
                id="room-type"
                value={form.room_type}
                onChange={(e) => setForm((f) => ({ ...f, room_type: e.target.value }))}
                placeholder="더블룸"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="sort-order">정렬 순서</Label>
              <TextInput
                id="sort-order"
                type="number"
                min={1}
                value={form.sort_order}
                onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) }))}
              />
            </div>

            <ToggleSwitch
              checked={form.is_active}
              onChange={(v) => setForm((f) => ({ ...f, is_active: v }))}
              label="활성화"
            />
          </div>
        </ModalBody>
        <ModalFooter>
          <Button color="blue" onClick={handleSubmit} disabled={saving}>
            {saving ? (
              <>
                <Spinner size="sm" className="mr-2" />
                저장 중...
              </>
            ) : (
              '저장'
            )}
          </Button>
          <Button color="light" onClick={() => setDialogOpen(false)}>취소</Button>
        </ModalFooter>
      </Modal>

      {/* Delete Confirm Modal */}
      <Modal show={!!deleteTarget} onClose={() => setDeleteTarget(null)} size="md" popup>
        <ModalHeader />
        <ModalBody>
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#FFEBEE] dark:bg-[#F04452]/10">
              <Trash2 className="h-6 w-6 text-[#F04452]" />
            </div>
            <h3 className="mb-2 text-[18px] font-semibold text-[#191F28] dark:text-white">객실 삭제</h3>
            <p className="mb-5 text-[14px] text-[#8B95A1]">
              객실 <strong>"{deleteTarget?.room_number}"</strong>을(를) 정말 삭제하시겠습니까?
              이 작업은 되돌릴 수 없습니다.
            </p>
            <div className="flex justify-center gap-3">
              <Button color="failure" onClick={confirmDelete}>삭제</Button>
              <Button color="light" onClick={() => setDeleteTarget(null)}>취소</Button>
            </div>
          </div>
        </ModalBody>
      </Modal>
    </div>
  );
};

export default RoomManagement;
