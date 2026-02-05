import { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Switch, message, Card } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { rulesAPI } from '../services/api';

const Rules = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    setLoading(true);
    try {
      const response = await rulesAPI.getAll();
      setRules(response.data);
    } catch (error) {
      console.error('Failed to load rules:', error);
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

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '이름',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '패턴 (정규식)',
      dataIndex: 'pattern',
      key: 'pattern',
      ellipsis: true,
    },
    {
      title: '응답',
      dataIndex: 'response',
      key: 'response',
      ellipsis: true,
    },
    {
      title: '우선순위',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
    },
    {
      title: '활성화',
      dataIndex: 'active',
      key: 'active',
      width: 100,
      render: (active: boolean) => (
        <Switch checked={active} disabled />
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
      <h1>룰 관리</h1>

      <Card style={{ marginTop: 24 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreate}
          style={{ marginBottom: 16 }}
        >
          룰 추가
        </Button>

        <Table
          dataSource={rules}
          columns={columns}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Modal
        title={editingId ? '룰 수정' : '룰 추가'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="이름"
            rules={[{ required: true, message: '이름을 입력하세요' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="pattern"
            label="패턴 (정규식)"
            rules={[{ required: true, message: '패턴을 입력하세요' }]}
          >
            <Input placeholder="(영업시간|몇시|언제)" />
          </Form.Item>
          <Form.Item
            name="response"
            label="응답"
            rules={[{ required: true, message: '응답을 입력하세요' }]}
          >
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item
            name="priority"
            label="우선순위"
            initialValue={0}
            rules={[{ required: true }]}
          >
            <InputNumber min={0} max={100} />
          </Form.Item>
          <Form.Item
            name="active"
            label="활성화"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Rules;
