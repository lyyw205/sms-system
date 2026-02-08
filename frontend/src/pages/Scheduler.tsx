import { useEffect, useState } from 'react';
import { Card, Table, Tag, Button, Space, Badge, message, Typography, Row, Col } from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { schedulerAPI } from '../services/api';

const { Title } = Typography;

const JOB_NAME_MAP: Record<string, string> = {
  sync_naver_reservations: '네이버 예약 동기화',
  send_party_guide: '파티 안내 자동 발송',
  extract_gender_stats: '성비 통계 추출',
};

const Scheduler = () => {
  const [jobs, setJobs] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [jobsRes, statusRes] = await Promise.all([
        schedulerAPI.getJobs(),
        schedulerAPI.getStatus(),
      ]);
      setJobs(jobsRes.data.jobs || []);
      setStatus(statusRes.data);
    } catch (error) {
      console.error('Failed to load scheduler data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRunJob = async (jobId: string) => {
    try {
      await schedulerAPI.runJob(jobId);
      message.success(`${JOB_NAME_MAP[jobId] || jobId} 수동 실행됨`);
      loadData();
    } catch (error) {
      message.error('잡 실행 실패');
    }
  };

  const handlePauseJob = async (jobId: string) => {
    try {
      await schedulerAPI.pauseJob(jobId);
      message.success(`${JOB_NAME_MAP[jobId] || jobId} 일시정지됨`);
      loadData();
    } catch (error) {
      message.error('잡 일시정지 실패');
    }
  };

  const handleResumeJob = async (jobId: string) => {
    try {
      await schedulerAPI.resumeJob(jobId);
      message.success(`${JOB_NAME_MAP[jobId] || jobId} 재개됨`);
      loadData();
    } catch (error) {
      message.error('잡 재개 실패');
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 220,
      render: (id: string) => <code>{id}</code>,
    },
    {
      title: '이름',
      dataIndex: 'id',
      key: 'name',
      render: (id: string, record: any) => JOB_NAME_MAP[id] || record.name || id,
    },
    {
      title: '다음 실행',
      dataIndex: 'next_run',
      key: 'next_run',
      render: (v: string) => v ? new Date(v).toLocaleString('ko-KR') : <Tag color="orange">일시정지</Tag>,
    },
    {
      title: '트리거',
      dataIndex: 'trigger',
      key: 'trigger',
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '상태',
      key: 'status',
      render: (_: any, record: any) => (
        record.next_run
          ? <Tag color="green">활성</Tag>
          : <Tag color="orange">일시정지</Tag>
      ),
    },
    {
      title: '작업',
      key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => handleRunJob(record.id)}
          >
            실행
          </Button>
          {record.next_run ? (
            <Button
              size="small"
              icon={<PauseCircleOutlined />}
              onClick={() => handlePauseJob(record.id)}
            >
              정지
            </Button>
          ) : (
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => handleResumeJob(record.id)}
            >
              재개
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>스케줄러 관리</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Space>
              <span>스케줄러 상태:</span>
              {status?.running ? (
                <Badge status="success" text={<Tag icon={<CheckCircleOutlined />} color="success">실행중</Tag>} />
              ) : (
                <Badge status="error" text={<Tag icon={<CloseCircleOutlined />} color="error">중지됨</Tag>} />
              )}
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Space>
              <span>등록된 잡:</span>
              <strong>{status?.job_count || 0}개</strong>
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Button onClick={loadData} icon={<ReloadOutlined />}>
              새로고침
            </Button>
          </Card>
        </Col>
      </Row>

      <Card title="스케줄 잡 목록">
        <Table
          dataSource={jobs}
          columns={columns}
          loading={loading}
          rowKey="id"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
};

export default Scheduler;
