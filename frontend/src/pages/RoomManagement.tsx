import { useEffect, useState, DragEvent } from 'react';
import { Button, Space, Modal, Form, Input, message, Card, Switch, InputNumber, Tag, Spin } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  HomeOutlined,
  HolderOutlined,
} from '@ant-design/icons';
import { roomsAPI } from '../services/api';

const RoomManagement = () => {
  const [rooms, setRooms] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadRooms();
  }, []);

  const loadRooms = async () => {
    setLoading(true);
    try {
      const response = await roomsAPI.getAll({ include_inactive: true });
      setRooms(response.data);
    } catch (error) {
      console.error('Failed to load rooms:', error);
      message.error('객실 목록 로드 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      is_active: true,
      sort_order: rooms.length + 1,
    });
    setModalVisible(true);
  };

  const handleEdit = (record: any) => {
    setEditingId(record.id);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleDelete = async (id: number, roomNumber: string) => {
    Modal.confirm({
      title: '객실 삭제',
      content: `객실 "${roomNumber}"을(를) 정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`,
      okText: '삭제',
      okType: 'danger',
      cancelText: '취소',
      onOk: async () => {
        try {
          await roomsAPI.delete(id);
          message.success('삭제 완료');
          loadRooms();
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '삭제 실패');
        }
      },
    });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingId) {
        await roomsAPI.update(editingId, values);
        message.success('수정 완료');
      } else {
        await roomsAPI.create(values);
        message.success('추가 완료');
      }
      setModalVisible(false);
      loadRooms();
    } catch (error: any) {
      if (error?.response?.data?.detail) {
        message.error(error.response.data.detail);
      } else {
        message.error('저장 실패');
      }
    }
  };

  // Drag and drop handlers
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

    const sourceIndex = parseInt(e.dataTransfer.getData('text/plain'));

    // Calculate actual insert position
    let targetIndex = insertIndex;
    if (sourceIndex < insertIndex) {
      targetIndex = insertIndex - 1;
    }

    if (sourceIndex === targetIndex) return;

    // Reorder rooms array
    const newRooms = [...rooms];
    const [movedRoom] = newRooms.splice(sourceIndex, 1);
    newRooms.splice(targetIndex, 0, movedRoom);

    // Update sort_order for all affected rooms
    const updates = newRooms.map((room, idx) => ({
      id: room.id,
      sort_order: idx + 1,
    }));

    try {
      // Update all rooms with new sort order
      await Promise.all(
        updates.map(({ id, sort_order }) =>
          roomsAPI.update(id, { sort_order })
        )
      );
      message.success('정렬 순서 변경 완료');
      loadRooms();
    } catch (error) {
      message.error('정렬 순서 변경 실패');
    }
  };

  const renderDropZone = (insertIndex: number) => {
    const isActive = dragOverIndex === insertIndex && draggingIndex !== null;

    return (
      <div
        key={`drop-${insertIndex}`}
        onDragOver={(e) => onDropZoneDragOver(e, insertIndex)}
        onDragLeave={onDropZoneDragLeave}
        onDrop={(e) => onDropZoneDrop(e, insertIndex)}
        style={{
          height: isActive ? 40 : 8,
          transition: 'height 0.2s',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {isActive && (
          <div
            style={{
              width: '100%',
              height: 3,
              background: '#1890ff',
              borderRadius: 2,
            }}
          />
        )}
      </div>
    );
  };

  const renderRoomCard = (room: any, index: number) => {
    const isDragging = draggingIndex === index;

    return (
      <div
        key={room.id}
        draggable
        onDragStart={(e) => onDragStart(e, index)}
        onDragEnd={onDragEnd}
        style={{
          display: 'flex',
          borderRadius: 6,
          overflow: 'hidden',
          border: '1px solid #f0f0f0',
          background: '#fff',
          opacity: isDragging ? 0.5 : 1,
          transition: 'opacity 0.2s',
          cursor: 'grab',
          userSelect: 'none',
        }}
      >
        {/* Index column */}
        <div
          style={{
            width: 60,
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#fafafa',
            borderRight: '1px solid #f0f0f0',
            padding: '12px',
          }}
        >
          <HolderOutlined style={{ fontSize: 16, color: '#8c8c8c' }} />
          <span style={{ marginLeft: 8, fontWeight: 500 }}>{index + 1}</span>
        </div>

        {/* Room info section */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            padding: '12px 16px',
            gap: 16,
          }}
        >
          <div style={{ minWidth: 100 }}>
            <strong style={{ fontSize: 15 }}>{room.room_number}</strong>
          </div>
          <div style={{ minWidth: 120 }}>
            <Tag color="blue">{room.room_type}</Tag>
          </div>
          <div style={{ minWidth: 80 }}>
            {room.is_active ? (
              <Tag color="green">활성</Tag>
            ) : (
              <Tag color="default">비활성</Tag>
            )}
          </div>
          <div style={{ flex: 1, fontSize: 12, color: '#8c8c8c' }}>
            {new Date(room.created_at).toLocaleString('ko-KR')}
          </div>
          <Space>
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                handleEdit(room);
              }}
            />
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                handleDelete(room.id, room.room_number);
              }}
            />
          </Space>
        </div>
      </div>
    );
  };

  return (
    <div>
      <h1><HomeOutlined /> 객실 관리</h1>

      <Card>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            객실 추가
          </Button>
          <div style={{ color: '#8c8c8c', fontSize: 13 }}>
            <HolderOutlined style={{ marginRight: 4 }} />
            드래그하여 순서 변경
          </div>
        </div>

        <Spin spinning={loading}>
          <div style={{ background: '#fafafa', padding: 16, borderRadius: 8, minHeight: 300 }}>
            {rooms.length === 0 && !loading ? (
              <div style={{ textAlign: 'center', padding: 60, color: '#bfbfbf' }}>
                등록된 객실이 없습니다
              </div>
            ) : (
              <>
                {rooms.map((room, index) => (
                  <div key={room.id}>
                    {renderDropZone(index)}
                    {renderRoomCard(room, index)}
                  </div>
                ))}
                {renderDropZone(rooms.length)}
              </>
            )}
          </div>
        </Spin>
      </Card>

      <Modal
        title={editingId ? '객실 수정' : '객실 추가'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={500}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="room_number"
            label="객실 번호"
            rules={[{ required: true, message: '객실 번호를 입력하세요' }]}
            tooltip="예: A101, B205, 별관"
          >
            <Input placeholder="A101" />
          </Form.Item>
          <Form.Item
            name="room_type"
            label="객실 타입"
            rules={[{ required: true, message: '객실 타입을 입력하세요' }]}
            tooltip="예: 더블룸, 트윈룸, 패밀리룸"
          >
            <Input placeholder="더블룸" />
          </Form.Item>
          <Form.Item
            name="sort_order"
            label="정렬 순서"
            rules={[{ required: true, message: '정렬 순서를 입력하세요' }]}
            tooltip="낮은 숫자가 먼저 표시됩니다"
          >
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="is_active"
            label="활성화"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default RoomManagement;
