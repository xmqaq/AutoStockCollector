import React, { Component, ReactNode } from 'react';
import { Result, Button, Card } from 'antd';
import { ReloadOutlined, HomeOutlined } from '@ant-design/icons';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center', 
          minHeight: '100vh',
          padding: 24,
          background: '#0a0a0a'
        }}>
          <Card style={{ maxWidth: 500, textAlign: 'center' }}>
            <Result
              status="error"
              title="页面加载失败"
              subTitle={this.state.error?.message || '发生了未知错误，请尝试刷新页面'}
              extra={[
                <Button 
                  key="reload" 
                  type="primary" 
                  icon={<ReloadOutlined />}
                  onClick={this.handleReload}
                >
                  刷新页面
                </Button>,
                <Button 
                  key="home" 
                  icon={<HomeOutlined />}
                  onClick={this.handleGoHome}
                >
                  返回首页
                </Button>
              ]}
            />
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;