import React, { useState, useEffect } from 'react';
import {
  Tabs,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  message,
  Space,
  Tag,
  Badge,
  Popconfirm,
  Card,
  Checkbox,
  Radio,
  InputNumber,
  Typography,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  SyncOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { templatesAPI, templateSchedulesAPI, campaignsAPI } from '../services/api';

const { TextArea } = Input;
const { Option } = Select;
const { Text } = Typography;

interface Template {
  id: number;
  key: string;
  name: string;
  content: string;
  variables: string | null;
  category: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  schedule_count: number;
}

interface TemplateSchedule {
  id: number;
  template_id: number;
  template_name: string;
  template_key: string;
  schedule_name: string;
  schedule_type: string;
  hour: number | null;
  minute: number | null;
  day_of_week: string | null;
  interval_minutes: number | null;
  timezone: string;
  target_type: string;
  target_value: string | null;
  date_filter: string | null;
  sms_type: string;
  exclude_sent: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
  last_run: string | null;
  next_run: string | null;
}

const Templates: React.FC = () => {
  const [activeTab, setActiveTab] = useState('templates');

  // Templates state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [templateModalVisible, setTemplateModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [templateForm] = Form.useForm();

  // Schedules state
  const [schedules, setSchedules] = useState<TemplateSchedule[]>([]);
  const [loadingSchedules, setLoadingSchedules] = useState(false);
  const [scheduleModalVisible, setScheduleModalVisible] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<TemplateSchedule | null>(null);
  const [scheduleForm] = Form.useForm();
  const [previewTargets, setPreviewTargets] = useState<any[]>([]);
  const [previewModalVisible, setPreviewModalVisible] = useState(false);
  const [selectedScheduleType, setSelectedScheduleType] = useState('daily');

  // Campaign history state
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);

  // Fetch templates
  const fetchTemplates = async () => {
    setLoadingTemplates(true);
    try {
      const response = await templatesAPI.getAll();
      setTemplates(response.data);
    } catch (error) {
      message.error('❌ 템플릿 목록을 불러오지 못했습니다');
      console.error(error);
    } finally {
      setLoadingTemplates(false);
    }
  };

  // Fetch schedules
  const fetchSchedules = async () => {
    setLoadingSchedules(true);
    try {
      const response = await templateSchedulesAPI.getAll();
      setSchedules(response.data);
    } catch (error) {
      message.error('❌ 스케줄 목록을 불러오지 못했습니다');
      console.error(error);
    } finally {
      setLoadingSchedules(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
    fetchSchedules();
  }, []);

  // Load campaigns when tab changes
  useEffect(() => {
    if (activeTab === 'campaigns') {
      fetchCampaigns();
    }
  }, [activeTab]);

  // Fetch campaigns
  const fetchCampaigns = async () => {
    setLoadingCampaigns(true);
    try {
      const response = await campaignsAPI.getHistory();
      setCampaigns(response.data);
    } catch (error) {
      message.error('❌ 발송 이력을 불러오지 못했습니다');
      console.error(error);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  // Template CRUD operations
  const handleCreateTemplate = () => {
    setEditingTemplate(null);
    templateForm.resetFields();
    setTemplateModalVisible(true);
  };

  const handleEditTemplate = (template: Template) => {
    setEditingTemplate(template);
    templateForm.setFieldsValue(template);
    setTemplateModalVisible(true);
  };

  const handleSaveTemplate = async () => {
    try {
      const values = await templateForm.validateFields();

      if (editingTemplate) {
        await templatesAPI.update(editingTemplate.id, values);
        message.success('✅ 템플릿이 수정되었습니다');
      } else {
        await templatesAPI.create(values);
        message.success('✅ 템플릿이 생성되었습니다');
      }

      setTemplateModalVisible(false);
      fetchTemplates();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '❌ 템플릿 저장 실패');
      console.error(error);
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    try {
      await templatesAPI.delete(id);
      message.success('✅ 템플릿이 삭제되었습니다');
      fetchTemplates();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '❌ 템플릿 삭제 실패');
    }
  };

  // Schedule CRUD operations
  const handleCreateSchedule = () => {
    setEditingSchedule(null);
    scheduleForm.resetFields();
    scheduleForm.setFieldsValue({
      schedule_type: 'daily',
      timezone: 'Asia/Seoul',
      target_type: 'all',
      sms_type: 'room',
      exclude_sent: true,
      active: true,
    });
    setSelectedScheduleType('daily');
    setScheduleModalVisible(true);
  };

  const handleEditSchedule = (schedule: TemplateSchedule) => {
    setEditingSchedule(schedule);
    scheduleForm.setFieldsValue(schedule);
    setSelectedScheduleType(schedule.schedule_type);
    setScheduleModalVisible(true);
  };

  const handleSaveSchedule = async () => {
    try {
      const values = await scheduleForm.validateFields();

      if (editingSchedule) {
        await templateSchedulesAPI.update(editingSchedule.id, values);
        message.success('✅ 스케줄이 수정되었습니다');
      } else {
        await templateSchedulesAPI.create(values);
        message.success('✅ 스케줄이 생성되었습니다');
      }

      setScheduleModalVisible(false);
      fetchSchedules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '❌ 스케줄 저장 실패');
      console.error(error);
    }
  };

  const handleDeleteSchedule = async (id: number) => {
    try {
      await templateSchedulesAPI.delete(id);
      message.success('✅ 스케줄이 삭제되었습니다');
      fetchSchedules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '❌ 스케줄 삭제 실패');
    }
  };

  const handleRunSchedule = async (id: number) => {
    try {
      message.loading({ content: '⏳ 실행 중...', key: 'run' });
      const response = await templateSchedulesAPI.run(id);
      message.success({
        content: `✅ 실행 완료: ${response.data.sent_count}명 발송, ${response.data.failed_count}명 실패`,
        key: 'run',
        duration: 5,
      });
      fetchSchedules();
    } catch (error: any) {
      message.error({ content: '❌ 실행 실패', key: 'run' });
    }
  };

  const handlePreviewTargets = async (id: number) => {
    try {
      const response = await templateSchedulesAPI.preview(id);
      setPreviewTargets(response.data);
      setPreviewModalVisible(true);
    } catch (error) {
      message.error('❌ 대상 미리보기 실패');
    }
  };

  const handleSyncSchedules = async () => {
    try {
      message.loading({ content: '⏳ 동기화 중...', key: 'sync' });
      const response = await templateSchedulesAPI.sync();
      message.success({
        content: `✅ ${response.data.message}`,
        key: 'sync',
        duration: 2,
      });
      fetchSchedules();
    } catch (error) {
      message.error({ content: '❌ 동기화 실패', key: 'sync' });
    }
  };

  // Template columns
  const templateColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '템플릿 키',
      dataIndex: 'key',
      key: 'key',
      width: 150,
      render: (key: string) => <code style={{ color: '#1890ff' }}>{key}</code>,
    },
    {
      title: '템플릿 이름',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: '카테고리',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (category: string) => category && <Tag color="blue">{category}</Tag>,
    },
    {
      title: '사용 변수',
      dataIndex: 'variables',
      key: 'variables',
      width: 200,
      render: (variables: string) => {
        if (!variables) return <Text type="secondary">없음</Text>;
        const varList = variables.split(',').map(v => v.trim());
        return (
          <Space size={[0, 4]} wrap>
            {varList.map((v, i) => (
              <Tag key={i} color="green">
                {v}
              </Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: '활성 상태',
      dataIndex: 'active',
      key: 'active',
      width: 100,
      render: (active: boolean) => (
        <Badge status={active ? 'success' : 'default'} text={active ? '활성' : '비활성'} />
      ),
    },
    {
      title: '연결된 스케줄',
      dataIndex: 'schedule_count',
      key: 'schedule_count',
      width: 120,
      render: (count: number) => <Badge count={count} showZero style={{ backgroundColor: '#52c41a' }} />,
    },
    {
      title: '작업',
      key: 'actions',
      width: 150,
      render: (_: any, record: Template) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditTemplate(record)}
          >
            수정
          </Button>
          <Popconfirm
            title="템플릿을 삭제하시겠습니까?"
            description={
              record.schedule_count > 0
                ? `이 템플릿에 ${record.schedule_count}개의 스케줄이 연결되어 있습니다. 정말 삭제하시겠습니까?`
                : '정말로 삭제하시겠습니까?'
            }
            onConfirm={() => handleDeleteTemplate(record.id)}
            okText="삭제"
            cancelText="취소"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              삭제
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // Campaign columns
  const campaignColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '발송 타입',
      dataIndex: 'campaign_type',
      key: 'campaign_type',
      width: 140,
      render: (type: string) => {
        const typeMap: Record<string, { color: string; label: string }> = {
          room_guide: { color: 'blue', label: '🏠 객실안내' },
          party_guide: { color: 'purple', label: '🎉 파티안내' },
          tag_based: { color: 'orange', label: '🏷️ 태그발송' },
          template_schedule_파티안내: { color: 'magenta', label: '⏰ 자동발송(파티)' },
          template_schedule_객실안내: { color: 'cyan', label: '⏰ 자동발송(객실)' },
        };
        const config = typeMap[type] || { color: 'default', label: type };
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: '대상 태그',
      dataIndex: 'target_tag',
      key: 'target_tag',
      width: 120,
      render: (tag: string) => tag ? <Tag color="geekblue">{tag}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '대상 수',
      dataIndex: 'target_count',
      key: 'target_count',
      width: 100,
    },
    {
      title: '성공',
      dataIndex: 'sent_count',
      key: 'sent_count',
      width: 80,
      render: (count: number) => <Text style={{ color: '#52c41a', fontWeight: 'bold' }}>{count}</Text>,
    },
    {
      title: '실패',
      dataIndex: 'failed_count',
      key: 'failed_count',
      width: 80,
      render: (count: number) =>
        count > 0 ? (
          <Text style={{ color: '#ff4d4f', fontWeight: 'bold' }}>{count}</Text>
        ) : (
          <Text type="secondary">0</Text>
        ),
    },
    {
      title: '발송 일시',
      dataIndex: 'sent_at',
      key: 'sent_at',
      width: 180,
      render: (sentAt: string) => {
        if (!sentAt) return <Text type="secondary">-</Text>;
        const date = new Date(sentAt);
        return <Text>{date.toLocaleString('ko-KR')}</Text>;
      },
    },
  ];

  // Schedule columns
  const scheduleColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '스케줄 이름',
      dataIndex: 'schedule_name',
      key: 'schedule_name',
      width: 180,
    },
    {
      title: '사용 템플릿',
      dataIndex: 'template_name',
      key: 'template_name',
      width: 150,
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: '발송 주기',
      dataIndex: 'schedule_type',
      key: 'schedule_type',
      width: 100,
      render: (type: string) => {
        const typeMap: Record<string, { label: string; color: string }> = {
          daily: { label: '매일', color: 'blue' },
          weekly: { label: '매주', color: 'green' },
          hourly: { label: '매시간', color: 'orange' },
          interval: { label: '간격', color: 'purple' },
        };
        const config = typeMap[type] || { label: type, color: 'default' };
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: '발송 시간',
      key: 'schedule',
      width: 200,
      render: (_: any, record: TemplateSchedule) => {
        if (record.schedule_type === 'daily') {
          return `매일 ${record.hour}시 ${String(record.minute).padStart(2, '0')}분`;
        } else if (record.schedule_type === 'weekly') {
          const dayMap: Record<string, string> = {
            mon: '월', tue: '화', wed: '수', thu: '목',
            fri: '금', sat: '토', sun: '일'
          };
          const days = record.day_of_week?.split(',').map(d => dayMap[d.trim()] || d).join(', ');
          return `${days}요일 ${record.hour}시 ${String(record.minute).padStart(2, '0')}분`;
        } else if (record.schedule_type === 'hourly') {
          return `매시간 ${String(record.minute).padStart(2, '0')}분`;
        } else if (record.schedule_type === 'interval') {
          return `${record.interval_minutes}분마다`;
        }
        return '-';
      },
    },
    {
      title: '발송 대상',
      key: 'target',
      width: 150,
      render: (_: any, record: TemplateSchedule) => {
        const targetLabels: Record<string, { label: string; color: string }> = {
          all: { label: '전체', color: 'default' },
          tag: { label: `태그: ${record.target_value}`, color: 'cyan' },
          room_assigned: { label: '객실배정자', color: 'blue' },
          party_only: { label: '파티만', color: 'magenta' },
        };
        const config = targetLabels[record.target_type] || { label: record.target_type, color: 'default' };
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: '다음 실행',
      dataIndex: 'next_run',
      key: 'next_run',
      width: 180,
      render: (nextRun: string | null) => {
        if (!nextRun) return <Text type="secondary">-</Text>;
        const date = new Date(nextRun);
        const now = new Date();
        const diff = date.getTime() - now.getTime();
        const minutes = Math.floor(diff / 60000);

        if (minutes < 60) {
          return <Text type="warning" strong>{minutes}분 후</Text>;
        }
        return <Text>{date.toLocaleString('ko-KR')}</Text>;
      },
    },
    {
      title: '상태',
      dataIndex: 'active',
      key: 'active',
      width: 80,
      render: (active: boolean) => (
        <Badge status={active ? 'processing' : 'default'} text={active ? '활성' : '비활성'} />
      ),
    },
    {
      title: '작업',
      key: 'actions',
      width: 220,
      render: (_: any, record: TemplateSchedule) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditSchedule(record)}
            title="스케줄 수정"
          >
            수정
          </Button>
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => handleRunSchedule(record.id)}
            title="지금 즉시 실행"
          >
            실행
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handlePreviewTargets(record.id)}
            title="발송 대상 미리보기"
          >
            미리보기
          </Button>
          <Popconfirm
            title="스케줄을 삭제하시겠습니까?"
            description="삭제하면 자동 발송이 중단됩니다."
            onConfirm={() => handleDeleteSchedule(record.id)}
            okText="삭제"
            cancelText="취소"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} title="스케줄 삭제">
              삭제
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // Render schedule fields based on type
  const renderScheduleFields = () => {
    const type = selectedScheduleType;

    if (type === 'daily') {
      return (
        <>
          <Form.Item
            label="시 (Hour)"
            name="hour"
            rules={[{ required: true, message: '시를 선택하세요' }]}
            extra={<Text type="secondary">💡 매일 이 시간에 발송됩니다</Text>}
          >
            <Select placeholder="시 선택" size="large" style={{ width: '100%' }}>
              {Array.from({ length: 24 }, (_, i) => (
                <Option key={i} value={i}>
                  {String(i).padStart(2, '0')}시
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="분 (Minute)"
            name="minute"
            rules={[{ required: true, message: '분을 선택하세요' }]}
          >
            <Select placeholder="분 선택" size="large" style={{ width: '100%' }}>
              {Array.from({ length: 60 }, (_, i) => (
                <Option key={i} value={i}>
                  {String(i).padStart(2, '0')}분
                </Option>
              ))}
            </Select>
          </Form.Item>
        </>
      );
    } else if (type === 'weekly') {
      return (
        <>
          <Form.Item
            label="요일"
            name="day_of_week"
            rules={[{ required: true, message: '요일을 선택하세요' }]}
            extra={<Text type="secondary">💡 선택한 요일마다 발송됩니다 (여러 개 선택 가능)</Text>}
          >
            <Select mode="multiple" placeholder="요일 선택 (복수 선택 가능)" size="large">
              <Option value="mon">월요일</Option>
              <Option value="tue">화요일</Option>
              <Option value="wed">수요일</Option>
              <Option value="thu">목요일</Option>
              <Option value="fri">금요일</Option>
              <Option value="sat">토요일</Option>
              <Option value="sun">일요일</Option>
            </Select>
          </Form.Item>
          <Form.Item
            label="시 (Hour)"
            name="hour"
            rules={[{ required: true, message: '시를 선택하세요' }]}
          >
            <Select placeholder="시 선택" size="large">
              {Array.from({ length: 24 }, (_, i) => (
                <Option key={i} value={i}>
                  {String(i).padStart(2, '0')}시
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="분 (Minute)"
            name="minute"
            rules={[{ required: true, message: '분을 선택하세요' }]}
          >
            <Select placeholder="분 선택" size="large">
              {Array.from({ length: 60 }, (_, i) => (
                <Option key={i} value={i}>
                  {String(i).padStart(2, '0')}분
                </Option>
              ))}
            </Select>
          </Form.Item>
        </>
      );
    } else if (type === 'hourly') {
      return (
        <Form.Item
          label="분 (Minute)"
          name="minute"
          rules={[{ required: true, message: '분을 선택하세요' }]}
          extra={<Text type="secondary">💡 매시간 이 분에 발송됩니다 (예: 10분 → 1:10, 2:10, 3:10...)</Text>}
        >
          <Select placeholder="분 선택" size="large">
            {Array.from({ length: 60 }, (_, i) => (
              <Option key={i} value={i}>
                매시간 {String(i).padStart(2, '0')}분
              </Option>
            ))}
          </Select>
        </Form.Item>
      );
    } else if (type === 'interval') {
      return (
        <Form.Item
          label="간격 (분)"
          name="interval_minutes"
          rules={[{ required: true, message: '간격을 입력하세요' }]}
          extra={<Text type="secondary">💡 N분마다 반복 발송됩니다 (예: 10분 → 10분마다 발송)</Text>}
        >
          <InputNumber
            min={1}
            max={1440}
            placeholder="예: 10"
            size="large"
            style={{ width: '100%' }}
            addonAfter="분마다"
          />
        </Form.Item>
      );
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Card title="📝 메시지 템플릿 및 스케줄 관리">
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'templates',
              label: '📄 템플릿 관리',
              children: (
                <>
                  <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
                    <Text type="secondary">
                      💡 메시지 템플릿을 만들어두면 스케줄에서 자동으로 발송할 수 있습니다.
                      변수를 사용하면 고객 이름, 객실 번호 등을 자동으로 채워줍니다.
                    </Text>
                    <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateTemplate} size="large">
                      새 템플릿 만들기
                    </Button>
                  </Space>

                  <Table
                    columns={templateColumns}
                    dataSource={templates}
                    loading={loadingTemplates}
                    rowKey="id"
                    pagination={{ pageSize: 10 }}
                    scroll={{ x: 1200 }}
                  />
                </>
              ),
            },
            {
              key: 'schedules',
              label: '⏰ 발송 스케줄',
              children: (
                <>
                  <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
                    <Text type="secondary">
                      💡 템플릿을 자동으로 발송할 시간을 설정합니다.
                      매일, 매주, 매시간, 또는 N분마다 발송할 수 있습니다.
                    </Text>
                    <Space>
                      <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateSchedule} size="large">
                        새 스케줄 만들기
                      </Button>
                      <Button icon={<SyncOutlined />} onClick={handleSyncSchedules}>
                        스케줄러 동기화
                      </Button>
                    </Space>
                  </Space>

                  <Table
                    columns={scheduleColumns}
                    dataSource={schedules}
                    loading={loadingSchedules}
                    rowKey="id"
                    pagination={{ pageSize: 10 }}
                    scroll={{ x: 1400 }}
                  />
                </>
              ),
            },
            {
              key: 'campaigns',
              label: '📊 발송 이력',
              children: (
                <>
                  <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
                    <Text type="secondary">
                      💡 지금까지 발송한 메시지의 이력을 확인할 수 있습니다.
                      템플릿 스케줄로 발송된 메시지와 수동 발송 모두 기록됩니다.
                    </Text>
                    <Button
                      onClick={fetchCampaigns}
                      icon={<ReloadOutlined />}
                      loading={loadingCampaigns}
                    >
                      새로고침
                    </Button>
                  </Space>

                  <Table
                    dataSource={campaigns}
                    columns={campaignColumns}
                    loading={loadingCampaigns}
                    rowKey="id"
                    pagination={{ pageSize: 10 }}
                    scroll={{ x: 1000 }}
                  />
                </>
              ),
            },
          ]}
        />
      </Card>

      {/* Template Modal */}
      <Modal
        title={
          <Space>
            <span>{editingTemplate ? '📝 템플릿 수정' : '✨ 새 템플릿 만들기'}</span>
          </Space>
        }
        open={templateModalVisible}
        onOk={handleSaveTemplate}
        onCancel={() => setTemplateModalVisible(false)}
        okText="저장"
        cancelText="취소"
        width={750}
      >
        <Form form={templateForm} layout="vertical">
          <Form.Item
            label="템플릿 키 (Template Key)"
            name="key"
            rules={[
              { required: true, message: '템플릿 키를 입력하세요' },
              { pattern: /^[a-z_]+$/, message: '영문 소문자와 언더스코어(_)만 사용 가능합니다' },
            ]}
            extra={
              <Text type="secondary">
                💡 시스템에서 사용하는 고유 식별자입니다. 예: welcome_message, room_guide
              </Text>
            }
          >
            <Input placeholder="예: welcome_message" disabled={!!editingTemplate} />
          </Form.Item>

          <Form.Item
            label="템플릿 이름"
            name="name"
            rules={[{ required: true, message: '템플릿 이름을 입력하세요' }]}
            extra={<Text type="secondary">💡 관리자가 보는 이름입니다. 한글로 작성하세요.</Text>}
          >
            <Input placeholder="예: 환영 메시지" />
          </Form.Item>

          <Form.Item label="카테고리" name="category" extra={<Text type="secondary">💡 템플릿 분류용입니다. 선택하지 않아도 됩니다.</Text>}>
            <Select placeholder="카테고리 선택 (선택사항)" allowClear>
              <Option value="room_guide">🏠 객실 안내</Option>
              <Option value="party_guide">🎉 파티 안내</Option>
              <Option value="confirmation">✅ 예약 확인</Option>
              <Option value="reminder">⏰ 리마인더</Option>
              <Option value="other">📌 기타</Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="메시지 내용"
            name="content"
            rules={[{ required: true, message: '메시지 내용을 입력하세요' }]}
            extra={
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">
                  💡 <strong>변수 사용법:</strong> {`{{변수명}}`} 형식으로 작성하면 자동으로 값이 채워집니다
                </Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  예: {`{{customerName}}`}님, 객실은 {`{{roomNumber}}`}호입니다.
                </Text>
              </div>
            }
          >
            <TextArea
              rows={8}
              placeholder={`예시:\n안녕하세요 {{customerName}}님!\n금일 객실은 {{building}}동 {{roomNum}}호입니다.\n비밀번호: {{password}}\n\n즐거운 하루 되세요!`}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item
            label="사용 가능한 변수"
            name="variables"
            extra={
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">
                  💡 쉼표(,)로 구분하여 입력하세요
                </Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  자주 쓰는 변수: customerName(고객명), roomNumber(객실번호), building(동), roomNum(호수), password(비밀번호), date(날짜), time(시간)
                </Text>
              </div>
            }
          >
            <Input placeholder="예: customerName, roomNumber, password" />
          </Form.Item>

          <Form.Item label="활성 상태" name="active" valuePropName="checked" extra={<Text type="secondary">💡 비활성화하면 이 템플릿을 사용할 수 없습니다</Text>}>
            <Switch checkedChildren="활성" unCheckedChildren="비활성" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Schedule Modal */}
      <Modal
        title={
          <Space>
            <span>{editingSchedule ? '⏰ 스케줄 수정' : '🎯 새 발송 스케줄 만들기'}</span>
          </Space>
        }
        open={scheduleModalVisible}
        onOk={handleSaveSchedule}
        onCancel={() => setScheduleModalVisible(false)}
        okText="저장"
        cancelText="취소"
        width={750}
      >
        <Form form={scheduleForm} layout="vertical">
          <Form.Item
            label="스케줄 이름"
            name="schedule_name"
            rules={[{ required: true, message: '스케줄 이름을 입력하세요' }]}
            extra={<Text type="secondary">💡 관리하기 쉽게 알아보기 쉬운 이름을 지어주세요</Text>}
          >
            <Input placeholder="예: 파티 안내 자동 발송" />
          </Form.Item>

          <Form.Item
            label="발송할 템플릿"
            name="template_id"
            rules={[{ required: true, message: '템플릿을 선택하세요' }]}
            extra={<Text type="secondary">💡 위에서 만든 템플릿 중 하나를 선택하세요</Text>}
          >
            <Select placeholder="템플릿 선택" size="large">
              {templates.map((t) => (
                <Option key={t.id} value={t.id}>
                  📄 {t.name} <Text type="secondary">({t.key})</Text>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="발송 주기"
            name="schedule_type"
            rules={[{ required: true, message: '발송 주기를 선택하세요' }]}
            extra={<Text type="secondary">💡 메시지를 얼마나 자주 보낼지 선택하세요</Text>}
          >
            <Radio.Group onChange={(e) => setSelectedScheduleType(e.target.value)} size="large">
              <Radio.Button value="daily" style={{ minWidth: 100 }}>📅 매일</Radio.Button>
              <Radio.Button value="weekly" style={{ minWidth: 100 }}>📆 매주</Radio.Button>
              <Radio.Button value="hourly" style={{ minWidth: 100 }}>⏰ 매시간</Radio.Button>
              <Radio.Button value="interval" style={{ minWidth: 100 }}>⏱️ 간격</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {renderScheduleFields()}

          <Form.Item
            label="발송 대상"
            name="target_type"
            rules={[{ required: true, message: '발송 대상을 선택하세요' }]}
            extra={<Text type="secondary">💡 누구에게 메시지를 보낼지 선택하세요</Text>}
          >
            <Select placeholder="대상 선택" size="large">
              <Option value="all">👥 전체 예약자</Option>
              <Option value="tag">🏷️ 특정 태그가 있는 사람</Option>
              <Option value="room_assigned">🏠 객실이 배정된 사람</Option>
              <Option value="party_only">🎉 파티만 참석하는 사람</Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) =>
              prevValues.target_type !== currentValues.target_type
            }
          >
            {({ getFieldValue }) =>
              getFieldValue('target_type') === 'tag' ? (
                <Form.Item
                  label="태그 이름"
                  name="target_value"
                  rules={[{ required: true, message: '태그 이름을 입력하세요' }]}
                  extra={<Text type="secondary">💡 예약자에게 붙은 태그를 입력하세요 (예: 파티만, 1초, 2차만)</Text>}
                >
                  <Input placeholder="예: 파티만" />
                </Form.Item>
              ) : null
            }
          </Form.Item>

          <Form.Item
            label="날짜 필터"
            name="date_filter"
            extra={<Text type="secondary">💡 특정 날짜의 예약자에게만 보낼 수 있습니다</Text>}
          >
            <Select placeholder="필터 없음 (모든 날짜)" allowClear size="large">
              <Option value="today">📅 오늘 예약자</Option>
              <Option value="tomorrow">📆 내일 예약자</Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="SMS 유형"
            name="sms_type"
            extra={<Text type="secondary">💡 객실 안내는 room, 파티 안내는 party를 선택하세요</Text>}
          >
            <Radio.Group size="large">
              <Radio.Button value="room">🏠 객실 (Room)</Radio.Button>
              <Radio.Button value="party">🎉 파티 (Party)</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            label="중복 발송 방지"
            name="exclude_sent"
            valuePropName="checked"
            extra={<Text type="secondary">💡 이미 발송한 사람에게는 다시 보내지 않습니다</Text>}
          >
            <Checkbox>이미 발송된 대상은 제외</Checkbox>
          </Form.Item>

          <Form.Item
            label="활성 상태"
            name="active"
            valuePropName="checked"
            extra={<Text type="secondary">💡 비활성화하면 자동 발송이 중단됩니다</Text>}
          >
            <Switch checkedChildren="활성" unCheckedChildren="비활성" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Preview Targets Modal */}
      <Modal
        title="👥 발송 대상 미리보기"
        open={previewModalVisible}
        onCancel={() => setPreviewModalVisible(false)}
        footer={[
          <Button key="close" type="primary" onClick={() => setPreviewModalVisible(false)}>
            확인
          </Button>,
        ]}
        width={900}
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            💡 아래 사람들에게 메시지가 발송됩니다. 중복 발송 방지가 켜져있으면 '발송 완료'된 사람은 제외됩니다.
          </Text>
        </div>
        <Table
          dataSource={previewTargets}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          size="small"
          columns={[
            { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
            { title: '이름', dataIndex: 'customer_name', key: 'customer_name', width: 120 },
            { title: '전화번호', dataIndex: 'phone', key: 'phone', width: 130 },
            {
              title: '객실',
              dataIndex: 'room_number',
              key: 'room_number',
              width: 100,
              render: (room: string) => room || <Text type="secondary">-</Text>
            },
            {
              title: '발송 완료',
              key: 'sent',
              width: 120,
              render: (_: any, record: any) => (
                <Space>
                  {record.room_sms_sent && <Tag color="green">객실✓</Tag>}
                  {record.party_sms_sent && <Tag color="blue">파티✓</Tag>}
                  {!record.room_sms_sent && !record.party_sms_sent && <Text type="secondary">없음</Text>}
                </Space>
              ),
            },
          ]}
        />
        <div style={{ marginTop: 16, padding: '12px 16px', background: '#f0f5ff', borderRadius: 4 }}>
          <Text strong>총 {previewTargets.length}명</Text>에게 발송됩니다
        </div>
      </Modal>
    </div>
  );
};

export default Templates;
