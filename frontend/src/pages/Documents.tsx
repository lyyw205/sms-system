import { useEffect, useState } from 'react';
import { Table, Button, Upload, message, Card, Space } from 'antd';
import { UploadOutlined, DeleteOutlined, FileTextOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { documentsAPI } from '../services/api';

const Documents = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const response = await documentsAPI.getAll();
      setDocuments(response.data);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
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

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '파일명',
      dataIndex: 'filename',
      key: 'filename',
      render: (text: string) => (
        <Space>
          <FileTextOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '업로드 시간',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      render: (time: string) => new Date(time).toLocaleString('ko-KR'),
    },
    {
      title: '인덱싱',
      dataIndex: 'indexed',
      key: 'indexed',
      render: (indexed: boolean) => (indexed ? '✅ 완료' : '⏳ 대기중'),
    },
    {
      title: '작업',
      key: 'action',
      render: (record: any) => (
        <Button
          size="small"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleDelete(record.id)}
        />
      ),
    },
  ];

  return (
    <div>
      <h1>문서 관리</h1>

      <Card style={{ marginTop: 24 }}>
        <Upload {...uploadProps}>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            loading={uploading}
            style={{ marginBottom: 16 }}
          >
            문서 업로드
          </Button>
        </Upload>

        <p style={{ color: '#888', marginBottom: 16 }}>
          ⚠️ Demo Mode: 문서는 메타데이터만 저장되며 실제로 RAG 인덱싱되지 않습니다.
          <br />
          프로덕션 모드에서는 ChromaDB에 임베딩되어 LLM 응답 생성 시 활용됩니다.
        </p>

        <Table
          dataSource={documents}
          columns={columns}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
};

export default Documents;
