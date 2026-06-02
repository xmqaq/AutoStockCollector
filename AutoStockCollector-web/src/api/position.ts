// 模拟盘重构后，持仓接口已迁移至 paper.ts
// 此文件保留以免历史引用报错，直接重导出 paperApi
export { paperApi as positionApi, paperApi } from './paper'
export type { PaperPosition as Position } from './paper'