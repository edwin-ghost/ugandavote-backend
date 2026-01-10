-- ===========================================
-- USER INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_user_phone ON "user"(phone);
CREATE INDEX IF NOT EXISTS idx_user_referral_code ON "user"(referral_code);
CREATE INDEX IF NOT EXISTS idx_user_referred_by ON "user"(referred_by);
CREATE INDEX IF NOT EXISTS idx_user_created_at ON "user"(created_at);

-- ===========================================
-- BET INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_bet_user_id ON bet(user_id);
CREATE INDEX IF NOT EXISTS idx_bet_created_at ON bet(created_at);
CREATE INDEX IF NOT EXISTS idx_bet_status ON bet(status);
CREATE INDEX IF NOT EXISTS idx_bet_user_created ON bet(user_id, created_at);

-- ===========================================
-- BET SELECTION INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_bet_selection_bet_id ON bet_selection(bet_id);

-- ===========================================
-- WITHDRAWAL INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_withdrawal_user_id ON withdrawal(user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawal_status ON withdrawal(status);
CREATE INDEX IF NOT EXISTS idx_withdrawal_created_at ON withdrawal(created_at);
CREATE INDEX IF NOT EXISTS idx_withdrawal_user_status ON withdrawal(user_id, status);

-- ===========================================
-- MPESA TRANSACTION INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_mpesa_user_id ON mpesa_transaction(user_id);
CREATE INDEX IF NOT EXISTS idx_mpesa_checkout_request_id ON mpesa_transaction(checkout_request_id);
CREATE INDEX IF NOT EXISTS idx_mpesa_status ON mpesa_transaction(status);
CREATE INDEX IF NOT EXISTS idx_mpesa_phone ON mpesa_transaction(phone);
CREATE INDEX IF NOT EXISTS idx_mpesa_created_at ON mpesa_transaction(created_at);
CREATE INDEX IF NOT EXISTS idx_mpesa_user_status ON mpesa_transaction(user_id, status);

-- ===========================================
-- REFERRAL REWARD INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_referral_reward_referrer_id ON referral_reward(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referral_reward_referred_id ON referral_reward(referred_id);
CREATE INDEX IF NOT EXISTS idx_referral_reward_created_at ON referral_reward(created_at);

-- ===========================================
-- ELECTION INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_election_type ON election(type);

-- ===========================================
-- CANDIDATE INDEXES
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_candidate_election_id ON candidate(election_id);