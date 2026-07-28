export interface Transaction {
  id: string;
  merchant_id: string;
  sequence_no: number;
  amount: string;
  currency: string;
  transaction_type: "SALE" | "EXPENSE" | "SUPPLIER_PAYMENT";
  is_credit: boolean;
  customer_phone: string | null;
  record_hash: string;
  created_at: string;
}

export interface Product {
  id: string;
  merchant_id: string;
  name: string;
  unit_cost: string;
  unit_price: string;
  quantity_on_hand: number;
  reorder_threshold: number | null;
  updated_at: string;
}
