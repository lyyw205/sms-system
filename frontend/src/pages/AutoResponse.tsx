import { useEffect, useState } from 'react';
import {
  Tabs, Table, Button, Space, Modal, Form, Input, InputNumber, Switch,
  Upload, message, Card, Typography,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined,
  FileTextOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { rulesAPI, documentsAPI } from '../services/api';

const { Title } = Typography;

const AutoResponse = () => {
  // --- Rules state ---
  const [rules, setRules] = useState([]);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  // --- Documents state ---
  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadRules();
    loadDocuments();
  }, []);

  // ===================== Rules =====================

  const loadRules = async () => {
    setRulesLoading(true);
    try {
      const response = await rulesAPI.getAll();
      setRules(response.data);
    } catch (error) {
      console.error('Failed to load rules:', error);
    } finally {
      setRulesLoading(false);
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

  const handleDeleteRule = async (id: number) => {
    try {
      await rulesAPI.delete(id);
      message.success('룰 삭제 완료');
      loadRules();
    } catch (error) {
      message.error('룰 삭제 실패');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingId) {
        await rulesAPI.update(editingId, values);
        message.success('룰 수정 완료');
      } else {
        await rulesAPI.create(values);
        message.success('룰 생성 완료');
      }
      setModalVisible(false);
      loadRules();
    } catch (error) {
      message.error('룰 저장 실패');
    }
  };

  const rulesColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '이름', dataIndex: 'name', key: 'name' },
    { title: '패턴 (정규식)', dataIndex: 'pattern', key: 'pattern', ellipsis: true },
    { title: '응답', dataIndex: 'response', key: 'response', ellipsis: true },
    { title: '우선순위', dataIndex: 'priority', key: 'priority', width: 100 },
    {
      title: '활성화', dataIndex: 'active', key: 'active', width: 100,
      render: (active: boolean) => <Switch checked={active} disabled />,
    },
    {
      title: '작업', key: 'action',
      render: (record: any) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteRule(record.id)} />
        </Space>
      ),
    },
  ];

  // ===================== Documents =====================

  const loadDocuments = async () => {
    setDocsLoading(true);
    try {
      const response = await documentsAPI.getAll();
      setDocuments(response.data);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setDocsLoading(false);
    }
  };

  const handleDeleteDoc = async (id: number) => {
    try {
      await documentsAPI.delete(id);
      message.success('문서 삭제 완료');
      loadDocuments();
    } catch (error) {
      message.error('문서 삭제 실패');
    }
  };

  const uploadProps: UploadProps = {
    beforeUpload: async (file) => {
      setUploading(true);
      try {
        await documentsAPI.upload(file);
        message.success(`${file.name} 업로드 완료 (Mock 모드)`);
        loadDocuments();
      } catch (error) {
        message.error('업로드 실패');
      } finally {
        setUploading(false);
      }
      return false;
    },
    showUploadList: false,
  };

  const docsColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '파일명', dataIndex: 'filename', key: 'filename',
      render: (text: string) => (
        <Space><FileTextOutlined />{text}</Space>
      ),
    },
    {
      title: '업로드 시간', dataIndex: 'uploaded_at', key: 'uploaded_at',
      render: (time: string) => new Date(time).toLocaleString('ko-KR'),
    },
    {
      title: '인덱싱', dataIndex: 'indexed', key: 'indexed',
      render: (indexed: boolean) => (indexed ? '완료' : '대기중'),
    },
    {
      title: '작업', key: 'action',
      render: (record: any) => (
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteDoc(record.id)} />
      ),
    },
  ];

  // ===================== Tabs =====================

  const tabItems = [
    {
      key: 'rules',
      label: '응답 규칙',
      children: (
        <Card>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} style={{ marginBottom: 16 }}>
            룰 추가
          </Button>
          <Table dataSource={rules} columns={rulesColumns} loading={rulesLoading} rowKey="id" pagination={{ pageSize: 20 }} />
        </Card>
      ),
    },
    {
      key: 'documents',
      label: '지식 문서',
      children: (
        <Card>
          <Upload {...uploadProps}>
            <Button type="primary" icon={<UploadOutlined />} loading={uploading} style={{ marginBottom: 16 }}>
              문서 업로드
            </Button>
          </Upload>
          <p style={{ color: '#888', marginBottom: 16 }}>
            Demo Mode: 문서는 메타데이터만 저장되며 실제로 RAG 인덱싱되지 않습니다.
            <br />
            프로덕션 모드에서는 ChromaDB에 임베딩되어 LLM 응답 생성 시 활용됩니다.
          </p>
          <Table dataSource={documents} columns={docsColumns} loading={docsLoading} rowKey="id" pagination={{ pageSize: 20 }} />
        </Card>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}><ThunderboltOutlined /> 자동 응답 관리</Title>
      <Tabs items={tabItems} />

      <Modal
        title={editingId ? '룰 수정' : '룰 추가'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="이름" rules={[{ required: true, message: '이름을 입력하세요' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="pattern" label="패턴 (정규식)" rules={[{ required: true, message: '패턴을 입력하세요' }]}>
            <Input placeholder="(영업시간|몇시|언제)" />
          </Form.Item>
          <Form.Item name="response" label="응답" rules={[{ required: true, message: '응답을 입력하세요' }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="priority" label="우선순위" initialValue={0} rules={[{ required: true }]}>
            <InputNumber min={0} max={100} />
          </Form.Item>
          <Form.Item name="active" label="활성화" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AutoResponse;
