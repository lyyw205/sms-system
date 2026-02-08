import { useEffect, useState } from 'react';
import { Table, Tag, Button, Space, Modal, Form, Input, Select, message, Card } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SyncOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons';
import { reservationsAPI } from '../services/api';

const Reservations = () => {
  const [reservations, setReservations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadReservations();
  }, []);

  const loadReservations = async () => {
    setLoading(true);
    try {
      const response = await reservationsAPI.getAll({ limit: 100 });
      setReservations(response.data);
    } catch (error) {
      console.error('Failed to load reservations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: any) => {
    setEditingId(record.id);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await reservationsAPI.delete(id);
      message.success('예약 삭제 완료');
      loadReservations();
    } catch (error) {
      message.error('예약 삭제 실패');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingId) {
        await reservationsAPI.update(editingId, values);
        message.success('예약 수정 완료');
      } else {
        await reservationsAPI.create(values);
        message.success('예약 생성 완료');
      }
      setModalVisible(false);
      loadReservations();
    } catch (error) {
      message.error('예약 저장 실패');
    }
  };

  const handleSyncNaver = async () => {
    try {
      const response = await reservationsAPI.syncNaver();
      message.success(response.data.message);
      loadReservations();
    } catch (error) {
      message.error('네이버 동기화 실패');
    }
  };

  const handleSyncSheets = async () => {
    try {
      const response = await reservationsAPI.syncSheets();
      message.success(response.data.message);
    } catch (error) {
      message.error('Google Sheets 동기화 실패');
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '고객명',
      dataIndex: 'customer_name',
      key: 'customer_name',
    },
    {
      title: '전화번호',
      dataIndex: 'phone',
      key: 'phone',
    },
    {
      title: '예약 날짜',
      dataIndex: 'date',
      key: 'date',
    },
    {
      title: '시간',
      dataIndex: 'time',
      key: 'time',
    },
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          pending: 'blue',
          confirmed: 'green',
          cancelled: 'red',
          completed: 'default',
        };
        return <Tag color={colorMap[status]}>{status}</Tag>;
      },
    },
    {
      title: '객실',
      dataIndex: 'room_number',
      key: 'room_number',
      render: (v: string) => v ? <Tag color="cyan">{v}</Tag> : '-',
    },
    {
      title: '성별',
      dataIndex: 'gender',
      key: 'gender',
      render: (v: string) => v ? (
        <Tag color={v === '남' ? 'blue' : 'magenta'}>{v}</Tag>
      ) : '-',
    },
    {
      title: '태그',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string) => tags ? tags.split(',').map((t: string) => (
        <Tag key={t} color="orange">{t}</Tag>
      )) : '-',
    },
    {
      title: '객실문자',
      dataIndex: 'room_sms_sent',
      key: 'room_sms_sent',
      render: (v: boolean) => v ? <Tag color="green">발송완료</Tag> : <Tag>미발송</Tag>,
    },
    {
      title: '파티문자',
      dataIndex: 'party_sms_sent',
      key: 'party_sms_sent',
      render: (v: boolean) => v ? <Tag color="green">발송완료</Tag> : <Tag>미발송</Tag>,
    },
    {
      title: '출처',
      dataIndex: 'source',
      key: 'source',
      render: (source: string) => (
        <Tag color={source === 'naver' ? 'green' : 'default'}>{source}</Tag>
      ),
    },
    {
      title: '작업',
      key: 'action',
      render: (record: any) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <h1>예약 관리</h1>

      <Card style={{ marginTop: 24 }}>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            신규 예약
          </Button>
          <Button icon={<SyncOutlined />} onClick={handleSyncNaver}>
            네이버 예약 동기화
          </Button>
          <Button icon={<CloudUploadOutlined />} onClick={handleSyncSheets}>
            Google Sheets 동기화
          </Button>
        </Space>

        <Table
          dataSource={reservations}
          columns={columns}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1400 }}
          size="small"
        />
      </Card>

      <Modal
        title={editingId ? '예약 수정' : '신규 예약'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="customer_name"
            label="고객명"
            rules={[{ required: true, message: '고객명을 입력하세요' }]}
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
          <Form.Item
            name="date"
            label="예약 날짜"
            rules={[{ required: true, message: '날짜를 입력하세요' }]}
          >
            <Input type="date" />
          </Form.Item>
          <Form.Item
            name="time"
            label="시간"
            rules={[{ required: true, message: '시간을 입력하세요' }]}
          >
            <Input type="time" />
          </Form.Item>
          <Form.Item
            name="status"
            label="상태"
            initialValue="pending"
            rules={[{ required: true }]}
          >
            <Select>
              <Select.Option value="pending">대기중</Select.Option>
              <Select.Option value="confirmed">확정</Select.Option>
              <Select.Option value="cancelled">취소</Select.Option>
              <Select.Option value="completed">완료</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="notes" label="메모">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Reservations;
