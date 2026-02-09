import { useEffect, useState } from 'react';
import { Table, Tag, Button, Space, Modal, Form, Input, Select, message, Card, DatePicker, Row, Col, Statistic } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { reservationsAPI } from '../services/api';
import dayjs, { Dayjs } from 'dayjs';

const TAG_OPTIONS = ['1초', '2차만', '객후', '객후,1초', '1초,2차만'];

const Reservations = () => {
  const [reservations, setReservations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState<Dayjs>(dayjs());
  const [form] = Form.useForm();

  useEffect(() => {
    loadReservations();
  }, [selectedDate]);

  const loadReservations = async () => {
    setLoading(true);
    try {
      const response = await reservationsAPI.getAll({
        date: selectedDate.format('YYYY-MM-DD'),
        limit: 200
      });
      setReservations(response.data);
    } catch (error) {
      console.error('Failed to load reservations:', error);
      message.error('파티 신청자 목록 로드 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      date: selectedDate.format('YYYY-MM-DD'),
      time: '18:00',
      status: 'confirmed',
      source: 'manual',
    });
    setModalVisible(true);
  };

  const handleEdit = (record: any) => {
    setEditingId(record.id);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: '파티 신청자 삭제',
      content: '정말 삭제하시겠습니까?',
      onOk: async () => {
        try {
          await reservationsAPI.delete(id);
          message.success('삭제 완료');
          loadReservations();
        } catch (error) {
          message.error('삭제 실패');
        }
      },
    });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingId) {
        await reservationsAPI.update(editingId, values);
        message.success('수정 완료');
      } else {
        await reservationsAPI.create(values);
        message.success('신청자 추가 완료');
      }
      setModalVisible(false);
      loadReservations();
    } catch (error) {
      message.error('저장 실패');
    }
  };

  const maleCount = reservations.filter((r: any) => r.gender === '남').length;
  const femaleCount = reservations.filter((r: any) => r.gender === '여').length;
  const totalParticipants = reservations.reduce((sum: number, r: any) =>
    sum + (r.party_participants || 1), 0
  );

  const columns = [
    {
      title: '이름',
      dataIndex: 'customer_name',
      key: 'customer_name',
      width: 100,
    },
    {
      title: '전화번호',
      dataIndex: 'phone',
      key: 'phone',
      width: 130,
    },
    {
      title: '성별',
      dataIndex: 'gender',
      key: 'gender',
      width: 70,
      render: (v: string) => v ? (
        <Tag color={v === '남' ? 'blue' : 'magenta'}>{v}</Tag>
      ) : '-',
    },
    {
      title: '인원',
      dataIndex: 'party_participants',
      key: 'party_participants',
      width: 70,
      render: (v: number) => v || 1,
    },
    {
      title: '태그',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags: string) => {
        if (!tags) return '-';
        return tags.split(',').map((t: string) => (
          <Tag key={t} color="orange" style={{ marginBottom: 4 }}>
            {t.trim()}
          </Tag>
        ));
      },
    },
    {
      title: '객실',
      dataIndex: 'room_number',
      key: 'room_number',
      width: 100,
      render: (v: string) => v ? <Tag color="cyan">{v}</Tag> : <Tag color="default">미배정</Tag>,
    },
    {
      title: '메모',
      dataIndex: 'notes',
      key: 'notes',
      ellipsis: true,
    },
    {
      title: '작업',
      key: 'action',
      width: 100,
      fixed: 'right' as const,
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
      <h1>파티 신청자 관리</h1>

      <Row gutter={16} align="middle" style={{ marginBottom: 20 }}>
        <Col>
          <DatePicker
            value={selectedDate}
            onChange={(d) => d && setSelectedDate(d)}
            style={{ width: 200 }}
          />
        </Col>
        <Col>
          <Statistic title="총 신청자" value={reservations.length} suffix="명" prefix={<UserOutlined />} />
        </Col>
        <Col>
          <Statistic
            title="남성"
            value={maleCount}
            suffix="명"
            valueStyle={{ color: '#1890ff' }}
          />
        </Col>
        <Col>
          <Statistic
            title="여성"
            value={femaleCount}
            suffix="명"
            valueStyle={{ color: '#eb2f96' }}
          />
        </Col>
        <Col>
          <Statistic
            title="총 참여 인원"
            value={totalParticipants}
            suffix="명"
          />
        </Col>
      </Row>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            파티 신청자 추가
          </Button>
        </Space>

        <Table
          dataSource={reservations}
          columns={columns}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 50 }}
          scroll={{ x: 1000 }}
          size="small"
        />
      </Card>

      <Modal
        title={editingId ? '파티 신청자 수정' : '파티 신청자 추가'}
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
            name="tags"
            label="태그"
            tooltip="쉼표로 구분하여 입력 (예: 1초,2차만)"
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
  );
};

export default Reservations;
