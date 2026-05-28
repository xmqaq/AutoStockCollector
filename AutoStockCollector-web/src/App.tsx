import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import StockDetail from './pages/StockDetail';
import DataMonitor from './pages/DataMonitor';
import DragonTiger from './pages/DragonTiger';
import FundFlow from './pages/FundFlow';
import MarginTrading from './pages/MarginTrading';
import SectorFlow from './pages/SectorFlow';
import News from './pages/News';

const darkTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#177ddc',
    colorBgBase: '#0a0a0a',
    colorBgContainer: '#1a1a1a',
    colorBorder: '#303030',
    colorText: '#fff',
    colorTextSecondary: '#8c8c8c',
    borderRadius: 6,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  },
  components: {
    Layout: {
      siderBg: '#141414',
      bodyBg: '#0a0a0a',
    },
    Menu: {
      darkItemBg: '#141414',
      darkItemColor: '#8c8c8c',
      darkItemHoverColor: '#fff',
      darkItemSelectedColor: '#fff',
      darkItemSelectedBg: '#177ddc',
    },
    Card: {
      colorBgContainer: '#1a1a1a',
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#262626',
      rowHoverBg: '#262626',
    },
  },
};

function App() {
  return (
    <ConfigProvider theme={darkTheme}>
      <Router>
        <MainLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/stock/:code" element={<StockDetail />} />
            <Route path="/stock" element={<StockDetail />} />
            <Route path="/monitor" element={<DataMonitor />} />
            <Route path="/dragon-tiger" element={<DragonTiger />} />
            <Route path="/fund-flow" element={<FundFlow />} />
            <Route path="/margin" element={<MarginTrading />} />
            <Route path="/sector" element={<SectorFlow />} />
            <Route path="/news" element={<News />} />
          </Routes>
        </MainLayout>
      </Router>
    </ConfigProvider>
  );
}

export default App;