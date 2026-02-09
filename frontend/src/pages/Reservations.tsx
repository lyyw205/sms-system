import { useEffect, useState } from 'react';
import { Table, Tag, Button, Space, Modal, Form, Input, Select, message, Card, DatePicker, Row, Col, Statistic, Tooltip } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import { reservationsAPI } from '../services/api';
import dayjs, { Dayjs } from 'dayjs';

const TAG_OPTIONS = ['1초', '2차만', '객후', '객후,1초', '1초,2차만'];

const Reservations = () => {
  const [reservations, setReservations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [dateFilter, setDateFilter] = useState<Dayjs | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [form] = Form.useForm();

  useEffect(() => {
    loadReservations();
  }, [dateFilter]);

  const loadReservations = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 500 };
      if (dateFilter) {
        params.date = dateFilter.format('YYYY-MM-DD');
      }
      const response = await reservationsAPI.getAll(params);
      setReservations(response.data);
    } catch (error) {
      console.error('Failed to load reservations:', error);
      message.error('예약 목록 로드 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncNaver = async () => {
    setSyncing(true);
    try {
      const response = await reservationsAPI.syncNaver();
      message.success(`네이버 예약 동기화 완료: ${response.data.added}건 추가`);
      loadReservations();
    } catch (error) {
      console.error('Failed to sync Naver reservations:', error);
      message.error('네이버 예약 동기화 실패');
    } finally {
      setSyncing(false);
    }
  };

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      date: (dateFilter || dayjs()).format('YYYY-MM-DD'),
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
      title: '예약 삭제',
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
        message.success('예약 수정 완료');
      } else {
        await reservationsAPI.create(values);
        message.success('예약 추가 완료');
      }
      setModalVisible(false);
      loadReservations();
    } catch (error) {
      message.error('저장 실패');
    }
  };

  // Filter reservations
  const filteredReservations = reservations.filter((r: any) => {
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    if (sourceFilter !== 'all' && r.source !== sourceFilter) return false;
    return true;
  });

  // Statistics
  const totalCount = filteredReservations.length;
  const confirmedCount = filteredReservations.filter((r: any) => r.status === 'confirmed').length;
  const pendingCount = filteredReservations.filter((r: any) => r.status === 'pending').length;
  const cancelledCount = filteredReservations.filter((r: any) => r.status === 'cancelled').length;
  const naverCount = filteredReservations.filter((r: any) => r.source === 'naver').length;

  const columns = [
    {
      title: '예약ID',
      dataIndex: 'external_id',
      key: 'external_id',
      width: 120,
      render: (v: string, record: any) => {
        if (!v) return <Tag color="default">수동</Tag>;
        return (
          <Tooltip title={`네이버 예약 ID: ${v}`}>
            <Tag color="green" icon={<ShopOutlined />}>
              {v.substring(0, 8)}...
            </Tag>
          </Tooltip>
        );
      },
    },
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
      title: '예약일시',
      key: 'datetime',
      width: 150,
      render: (record: any) => (
        <div>
          <div>{record.date}</div>
          <div style={{ fontSize: '12px', color: '#999' }}>{record.time}</div>
        </div>
      ),
    },
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const statusConfig: any = {
          confirmed: { color: 'green', icon: <CheckCircleOutlined />, text: '확정' },
          pending: { color: 'orange', icon: <ClockCircleOutlined />, text: '대기' },
          cancelled: { color: 'red', icon: <CloseCircleOutlined />, text: '취소' },
          completed: { color: 'blue', icon: <CheckCircleOutlined />, text: '완료' },
        };
        const config = statusConfig[status] || { color: 'default', text: status };
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.text}
          </Tag>
        );
      },
    },
    {
      title: '출처',
      dataIndex: 'source',
      key: 'source',
      width: 80,
      render: (source: string) => {
        const sourceConfig: any = {
          naver: { color: 'green', text: '네이버' },
          manual: { color: 'default', text: '수동' },
          phone: { color: 'blue', text: '전화' },
        };
        const config = sourceConfig[source] || { color: 'default', text: source };
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '객실',
      dataIndex: 'room_number',
      key: 'room_number',
      width: 100,
      render: (v: string, record: any) => {
        if (!v) return <Tag color="default">미배정</Tag>;
        return (
          <Tooltip title={record.room_info}>
            <Tag color="cyan">{v}</Tag>
          </Tooltip>
        );
      },
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
      width: 120,
      fixed: 'right' as const,
      render: (record: any) => {
        // 네이버 예약은 수정/삭제 불가 (읽기 전용)
        if (record.source === 'naver') {
          return <Tag color="default">네이버 관리</Tag>;
        }
        return (
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
        );
      },
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ marginBottom: 0 }}>📋 예약 관리</h1>
          <p style={{ color: '#999', marginTop: 4 }}>
            전체 예약 리스트 • 네이버 예약 자동 동기화 (10분마다)
            {dateFilter && ` • 필터: ${dateFilter.format('YYYY-MM-DD')}`}
          </p>
        </div>
        <Button
          type="primary"
          icon={<SyncOutlined spin={syncing} />}
          onClick={handleSyncNaver}
          loading={syncing}
          size="large"
        >
          네이버 예약 동기화
        </Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col>
          <Card size="small">
            <Statistic
              title="총 예약"
              value={totalCount}
              suffix="건"
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col>
          <Card size="small">
            <Statistic
              title="확정"
              value={confirmedCount}
              suffix="건"
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col>
          <Card size="small">
            <Statistic
              title="대기"
              value={pendingCount}
              suffix="건"
              valueStyle={{ color: '#faad14' }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col>
          <Card size="small">
            <Statistic
              title="취소"
              value={cancelledCount}
              suffix="건"
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col>
          <Card size="small">
            <Statistic
              title="네이버 예약"
              value={naverCount}
              suffix="건"
              valueStyle={{ color: '#52c41a' }}
              prefix={<ShopOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <DatePicker
            value={dateFilter}
            onChange={setDateFilter}
            placeholder="날짜 필터 (전체)"
            style={{ width: 200 }}
            allowClear
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 120 }}
          >
            <Select.Option value="all">전체 상태</Select.Option>
            <Select.Option value="confirmed">확정</Select.Option>
            <Select.Option value="pending">대기</Select.Option>
            <Select.Option value="cancelled">취소</Select.Option>
            <Select.Option value="completed">완료</Select.Option>
          </Select>
          <Select
            value={sourceFilter}
            onChange={setSourceFilter}
            style={{ width: 120 }}
          >
            <Select.Option value="all">전체 출처</Select.Option>
            <Select.Option value="naver">네이버</Select.Option>
            <Select.Option value="manual">수동</Select.Option>
            <Select.Option value="phone">전화</Select.Option>
          </Select>
          {dateFilter && (
            <Button onClick={() => setDateFilter(null)}>
              전체 보기
            </Button>
          )}
        </Space>

        <Table
          dataSource={filteredReservations}
          columns={columns}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 50 }}
          scroll={{ x: 1200 }}
          size="small"
        />
      </Card>

      <Modal
        title={editingId ? '예약 수정' : '예약 추가'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
        okText="저장"
        cancelText="취소"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="customer_name"
            label="예약자 이름"
            rules={[{ required: true, message: '예약자 이름을 입력하세요' }]}
          >
            <Input placeholder="홍길동" />
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
                label="예약 날짜"
                rules={[{ required: true, message: '예약 날짜를 선택하세요' }]}
              >
                <Input type="date" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="time"
                label="예약 시간"
                rules={[{ required: true, message: '예약 시간을 선택하세요' }]}
              >
                <Input type="time" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="status"
                label="예약 상태"
                initialValue="confirmed"
              >
                <Select>
                  <Select.Option value="pending">대기</Select.Option>
                  <Select.Option value="confirmed">확정</Select.Option>
                  <Select.Option value="cancelled">취소</Select.Option>
                  <Select.Option value="completed">완료</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="party_participants"
                label="인원 수"
                initialValue={1}
              >
                <Input type="number" min={1} placeholder="1" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="gender"
                label="성별"
              >
                <Select placeholder="성별 선택" allowClear>
                  <Select.Option value="남">남</Select.Option>
                  <Select.Option value="여">여</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="room_info"
                label="객실 타입"
              >
                <Input placeholder="더블룸, 트윈룸 등" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="tags"
            label="태그"
            tooltip="1초, 2차만, 객후 등의 태그를 선택하거나 입력하세요"
          >
            <Select
              mode="tags"
              placeholder="태그 선택 또는 입력"
              options={TAG_OPTIONS.map(tag => ({ value: tag, label: tag }))}
            />
          </Form.Item>
          <Form.Item name="notes" label="메모">
            <Input.TextArea rows={3} placeholder="예약 관련 메모나 요청사항" />
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
