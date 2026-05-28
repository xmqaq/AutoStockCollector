import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  FundOutlined,
  BankOutlined,
  PieChartOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  TrophyOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import styles from './MainLayout.module.css';

const { Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '总览仪表盘' },
  { key: '/stock/:code', icon: <FundOutlined />, label: '股票详情' },
  { key: '/dragon-tiger', icon: <TrophyOutlined />, label: '龙虎榜' },
  { key: '/fund-flow', icon: <DollarOutlined />, label: '资金流向' },
  { key: '/margin', icon: <BankOutlined />, label: '融资融券' },
  { key: '/sector', icon: <PieChartOutlined />, label: '板块数据' },
  { key: '/news', icon: <FileTextOutlined />, label: '新闻舆情' },
  { key: '/monitor', icon: <DatabaseOutlined />, label: '采集监控' },
];

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const getSelectedKey = () => {
    const path = location.pathname;
    if (path === '/') return '/';
    const match = menuItems.find((item) => 
      item.key !== '/' && path.startsWith(item.key.split('/:')[0])
    );
    return match ? match.key : '/';
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key !== '/stock/:code') {
      navigate(key);
    }
  };

  return (
    <Layout className={styles.layout}>
      <Sider width={220} className={styles.sider}>
        <div className={styles.logo}>AutoStock</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          onClick={handleMenuClick}
          className={styles.menu}
        />
      </Sider>
      <Layout>
        <Content className={styles.content}>{children}</Content>
      </Layout>
    </Layout>
  );
}