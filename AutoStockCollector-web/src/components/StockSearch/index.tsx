import React, { useState, useCallback } from 'react';
import { AutoComplete, Input } from 'antd';
import { useNavigate } from 'react-router-dom';
import { normalizeCode } from '@/utils/stockCode';

interface StockSearchProps {
  placeholder?: string;
  onSelect?: (code: string) => void;
  style?: React.CSSProperties;
}

const commonStocks = [
  { value: 'SH600000', label: '浦发银行 (600000)' },
  { value: 'SH600036', label: '招商银行 (600036)' },
  { value: 'SH600519', label: '贵州茅台 (600519)' },
  { value: 'SH601318', label: '中国平安 (601318)' },
  { value: 'SH601398', label: '工商银行 (601398)' },
  { value: 'SZ000001', label: '平安银行 (000001)' },
  { value: 'SZ000002', label: '万科A (000002)' },
  { value: 'SZ000858', label: '五粮液 (000858)' },
  { value: 'SZ300750', label: '宁德时代 (300750)' },
  { value: 'SZ300059', label: '东方财富 (300059)' },
];

export default function StockSearch({ placeholder = '输入股票代码', onSelect, style }: StockSearchProps) {
  const [options, setOptions] = useState<{ value: string; label: string }[]>(commonStocks);
  const navigate = useNavigate();

  const handleSearch = useCallback((value: string) => {
    if (!value || value.length < 1) {
      setOptions(commonStocks.slice(0, 5));
      return;
    }
    const digits = value.replace(/[^0-9]/g, '');
    if (digits.length >= 6) {
      const code = normalizeCode(value);
      setOptions([{ value: code, label: `${code} (${code.slice(0, 2) === 'SH' ? '上海' : '深圳'})` }]);
    } else {
      setOptions(
        commonStocks
          .filter((s) => s.label.includes(value) || s.value.includes(digits))
          .slice(0, 5)
      );
    }
  }, []);

  const handleSelect = useCallback(
    (code: string) => {
      if (onSelect) {
        onSelect(code);
      } else {
        navigate(`/stock/${code}`);
      }
    },
    [navigate, onSelect]
  );

  return (
    <AutoComplete
      options={options}
      onSearch={handleSearch}
      onSelect={handleSelect}
      placeholder={placeholder}
      style={{ width: 260, ...style }}
      filterOption={(input, option) =>
        (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
      }
    >
      <Input.Search enterButton />
    </AutoComplete>
  );
}