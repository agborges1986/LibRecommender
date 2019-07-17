import time
from operator import itemgetter
import functools
import numpy as np
from scipy.sparse import csr_matrix, coo_matrix
from scipy import sparse
from ..evaluate import rmse, MAP_at_k, accuracy
from ..utils.initializers import truncated_normal
try:
    import tensorflow as tf
except ModuleNotFoundError:
    print("you need tensorflow for tf-version of this model")
from tqdm import tqdm, trange


class ALS_rating:
    def __init__(self, n_factors=100, n_epochs=20, reg=5.0, task="rating", seed=42):
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.reg = reg
        self.task = task
        self.seed = seed

    def fit(self, dataset, verbose=1):
        np.random.seed(self.seed)
        self.dataset = dataset
        self.default_prediction = dataset.global_mean
        self.pu = truncated_normal(shape=(dataset.n_users, self.n_factors),
                                   mean=0.0, scale=0.05)
        self.qi = truncated_normal(shape=(dataset.n_items, self.n_factors),
                                   mean=0.0, scale=0.05)

        for epoch in range(1, self.n_epochs + 1):
            t0 = time.time()
            for u in dataset.train_user:
                u_items = np.array(list(dataset.train_user[u].keys()))
                u_labels = np.array(list(dataset.train_user[u].values()))
                u_labels_expand = np.expand_dims(u_labels, axis=1)
                yy_reg = self.qi[u_items].T.dot(self.qi[u_items]) + \
                         self.reg * np.eye(self.n_factors)
                r_y = np.sum(np.multiply(u_labels_expand, self.qi[u_items]), axis=0)
            #    self.pu[u] = np.linalg.inv(yy_reg).dot(r_y)
                self.pu[u] = np.linalg.solve(yy_reg, r_y)

            for i in dataset.train_item:
                i_users = np.array(list(dataset.train_item[i].keys()))
                i_labels = np.array(list(dataset.train_item[i].values()))
                i_labels_expand = np.expand_dims(i_labels, axis=1)
                xx_reg = self.pu[i_users].T.dot(self.pu[i_users]) + \
                         self.reg * np.eye(self.n_factors)
                r_x = np.sum(np.multiply(i_labels_expand, self.pu[i_users]), axis=0)
            #    self.qi[i] = np.linalg.inv(xx_reg).dot(r_x)
                self.qi[i] = np.linalg.solve(xx_reg, r_x)

            if verbose > 0 and epoch % 5 == 0 and self.task == "rating":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
                print("training rmse: ", rmse(self, dataset, "train"))
                print("test rmse: ", rmse(self, dataset, "test"))
            elif verbose > 0 and epoch % 5 == 0 and self.task == "ranking":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
                print("MAP@{}: {:.4f}".format(5, MAP_at_k(self, dataset, 5)))

        return self

    def predict(self, u, i):
        try:
            pred = np.dot(self.pu[u], self.qi[i])
            pred = np.clip(pred, 1, 5)
        except IndexError:
            pred = self.default_prediction
        return pred

    def recommend_user(self, u, n_rec, random_rec=False):
        unlabled_items = list(set(range(self.dataset.n_items)) - set(self.dataset.train_user[u]))
        if np.any(np.array(unlabled_items) > self.dataset.n_items):
            rank = [(j, self.predict(u, j)) for j in range(len(self.qi))
                    if j not in self.dataset.train_user[u]]
        else:
            pred = np.dot(self.pu[u], self.qi[unlabled_items].T)
            pred = np.clip(pred, 1, 5)
            rank = list(zip(unlabled_items, pred))

        if random_rec:
            item_pred_dict = {j: r for j, r in rank if r >= 4}
            item_list = list(item_pred_dict.keys())
            pred_list = list(item_pred_dict.values())
            p = [p / np.sum(pred_list) for p in pred_list]
            item_candidates = np.random.choice(item_list, n_rec, replace=False, p=p)
            reco = [(item, item_pred_dict[item]) for item in item_candidates]
            return reco
        else:
            rank.sort(key=itemgetter(1), reverse=True)
            return rank[:n_rec]


class ALS_ranking_76897:
    def __init__(self, n_factors=100, n_epochs=20, reg=5.0, task="rating", seed=42):
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.reg = reg
        self.task = task
        self.seed = seed

    def fit(self, dataset, verbose=1):
        np.random.seed(self.seed)
        self.dataset = dataset
        self.default_prediction = dataset.global_mean
        self.pu = truncated_normal(shape=(dataset.n_users, self.n_factors),
                                   mean=0.0, scale=0.05)
        self.qi = truncated_normal(shape=(dataset.n_items, self.n_factors),
                                   mean=0.0, scale=0.05)

        for epoch in range(1, self.n_epochs + 1):
            t0 = time.time()
            for u in dataset.train_user:
                u_items = dataset.train_item_implicit[np.where(dataset.train_user_implicit == u)]
                u_labels = dataset.train_label_implicit[np.where(dataset.train_user_implicit == u)]
                u_labels_expand = np.expand_dims(u_labels, axis=1)
                yy_reg = self.qi[u_items].T.dot(self.qi[u_items]) + \
                         self.reg * np.eye(self.n_factors)
                r_y = np.sum(np.multiply(u_labels_expand, self.qi[u_items]), axis=0)
                self.pu[u] = np.linalg.inv(yy_reg).dot(r_y)

            for i in dataset.train_item:
                i_users = dataset.train_user_implicit[np.where(dataset.train_item_implicit == i)]
                i_labels = dataset.train_label_implicit[np.where(dataset.train_item_implicit == i)]
                i_labels_expand = np.expand_dims(i_labels, axis=1)
                xx_reg = self.pu[i_users].T.dot(self.pu[i_users]) + \
                         self.reg * np.eye(self.n_factors)
                r_x = np.sum(np.multiply(i_labels_expand, self.pu[i_users]), axis=0)
                self.qi[i] = np.linalg.inv(xx_reg).dot(r_x)

            if verbose > 0 and epoch % 1 == 0 and self.task == "rating":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
                print("training rmse: ", rmse(self, dataset, "train"))
                print("test rmse: ", rmse(self, dataset, "test"))
            elif verbose > 0 and epoch % 1 == 0 and self.task == "ranking":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
            #    print("MAP@{}: {:.4f}".format(5, MAP_at_k(self, dataset, 5)))
                print("training accuracy: ", accuracy(self, dataset, "train"))
                print("test accuracy: ", accuracy(self, dataset, "test"))

        return self

    def predict(self, u, i):
        try:
            prob = 1 / (1 + np.exp(-np.dot(self.pu[u], self.qi[i])))
            pred = 1.0 if prob >= 0.5 else 0.0
        except IndexError:
            pred = self.default_prediction
        return pred

    def recommend_user(self, u, n_rec, random_rec=False):
        unlabled_items = list(set(range(self.dataset.n_items)) - set(self.dataset.train_user[u]))
        if np.any(np.array(unlabled_items) > self.dataset.n_items):
            rank = [(j, self.predict(u, j)) for j in range(len(self.qi))
                    if j not in self.dataset.train_user[u]]
        else:
            pred = np.dot(self.pu[u], self.qi[unlabled_items].T)
            pred = np.clip(pred, 1, 5)
            rank = list(zip(unlabled_items, pred))

        if random_rec:
            item_pred_dict = {j: r for j, r in rank if r >= 4}
            item_list = list(item_pred_dict.keys())
            pred_list = list(item_pred_dict.values())
            p = [p / np.sum(pred_list) for p in pred_list]
            item_candidates = np.random.choice(item_list, n_rec, replace=False, p=p)
            reco = [(item, item_pred_dict[item]) for item in item_candidates]
            return reco
        else:
            rank.sort(key=itemgetter(1), reverse=True)
            return rank[:n_rec]


class ALS_ranking_78978:
    def __init__(self, n_factors=100, n_epochs=20, reg=5.0, task="rating", seed=42):
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.reg = reg
        self.task = task
        self.seed = seed

    def fit(self, dataset, verbose=1):
        np.random.seed(self.seed)
        self.dataset = dataset
        self.default_prediction = dataset.global_mean
        self.X = truncated_normal(shape=(dataset.n_users, self.n_factors),
                                   mean=0.0, scale=0.05)
        self.Y = truncated_normal(shape=(dataset.n_items, self.n_factors),
                                   mean=0.0, scale=0.05)

        for epoch in range(1, self.n_epochs + 1):
            t0 = time.time()
            YtY = self.Y.T.dot(self.Y)
            for u in dataset.train_user:
                Cu_indices = list(dataset.train_user[u].keys())
                labels = list(dataset.train_user[u].values())
                Cu_values = np.array(labels) * 10.0
                pu_indices = list(dataset.train_user[u].keys())
                pu_values = np.ones(len(pu_indices))

                Cu = csr_matrix((Cu_values, (Cu_indices, Cu_indices)), shape=[dataset.n_items, dataset.n_items])
                pu = csr_matrix((pu_values, (pu_indices, np.zeros(len(pu_indices), dtype=int))),
                                shape=[dataset.n_items, 1])
                ycy_reg = YtY + np.dot(self.Y.T, Cu.dot(self.Y)) + self.reg * np.eye(self.n_factors)
                cupu = Cu.dot(pu).toarray().flatten()
                ycp = np.dot(self.Y.T, cupu)
            #    ycp = Cu.dot(pu).T.dot(self.Y).flatten()
                self.X[u] = np.linalg.solve(ycy_reg, ycp)

            XtX = self.X.T.dot(self.X)
            for i in dataset.train_item:
                Ci_indices = list(dataset.train_item[i].keys())
                labels = list(dataset.train_item[i].values())
                Ci_values = np.array(labels) * 10.0
                pi_indices = list(dataset.train_item[i].keys())
                pi_values = np.ones(len(pi_indices))

                Ci = csr_matrix((Ci_values, (Ci_indices, Ci_indices)), shape=[dataset.n_users, dataset.n_users])
                pi = csr_matrix((pi_values, (pi_indices, np.zeros(len(pi_indices), dtype=int))),
                                shape=[dataset.n_users, 1])
                xcx_reg = XtX + np.dot(self.X.T, Ci.dot(self.X)) + self.reg * np.eye(self.n_factors)
                cipi = Ci.dot(pi).toarray().flatten()
                xcp = np.dot(self.X.T, cipi)
                self.Y[i] = np.linalg.solve(xcx_reg, xcp)

            if verbose > 0 and epoch % 1 == 0 and self.task == "rating":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
                print("training rmse: ", rmse(self, dataset, "train"))
                print("test rmse: ", rmse(self, dataset, "test"))
            elif verbose > 0 and epoch % 1 == 0 and self.task == "ranking":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
            #    print("MAP@{}: {:.4f}".format(5, MAP_at_k(self, dataset, 5)))
                print("training accuracy: ", accuracy(self, dataset, "train"))
                print("test accuracy: ", accuracy(self, dataset, "test"))

        return self

    def predict(self, u, i):
        try:
            prob = 1 / (1 + np.exp(-np.dot(self.X[u], self.Y[i])))
            pred = 1.0 if prob >= 0.5 else 0.0
        except IndexError:
            pred = self.default_prediction
        return pred

    def recommend_user(self, u, n_rec, random_rec=False):
        unlabled_items = list(set(range(self.dataset.n_items)) - set(self.dataset.train_user[u]))
        if np.any(np.array(unlabled_items) > self.dataset.n_items):
            rank = [(j, self.predict(u, j)) for j in range(len(self.Y))
                    if j not in self.dataset.train_user[u]]
        else:
            pred = np.dot(self.X[u], self.Y[unlabled_items].T)
            pred = np.clip(pred, 1, 5)
            rank = list(zip(unlabled_items, pred))

        if random_rec:
            item_pred_dict = {j: r for j, r in rank if r >= 4}
            item_list = list(item_pred_dict.keys())
            pred_list = list(item_pred_dict.values())
            p = [p / np.sum(pred_list) for p in pred_list]
            item_candidates = np.random.choice(item_list, n_rec, replace=False, p=p)
            reco = [(item, item_pred_dict[item]) for item in item_candidates]
            return reco
        else:
            rank.sort(key=itemgetter(1), reverse=True)
            return rank[:n_rec]


class ALS_ranking_56765:
    def __init__(self, n_factors=100, n_epochs=20, reg=5.0, task="rating", seed=42, alpha=10):
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.reg = reg
        self.task = task
        self.seed = seed
        self.alpha = alpha

    def fit(self, dataset, verbose=1):
        np.random.seed(self.seed)
        self.dataset = dataset
        self.default_prediction = dataset.global_mean
        self.X = truncated_normal(shape=(dataset.n_users, self.n_factors),
                                   mean=0.0, scale=0.05)
        self.Y = truncated_normal(shape=(dataset.n_items, self.n_factors),
                                   mean=0.0, scale=0.05)

        for epoch in range(1, self.n_epochs + 1):
            t0 = time.time()
            YtY = self.Y.T.dot(self.Y)
            for u in dataset.train_user:
                Cui_indices = list(dataset.train_user[u].keys())
                labels = list(dataset.train_user[u].values())
                Cui_values = np.array(labels) * self.alpha
                Cui = csr_matrix((Cui_values, (Cui_indices, Cui_indices)), shape=[dataset.n_items, dataset.n_items])

                pu_indices = list(dataset.train_user[u].keys())
                pu = np.zeros(dataset.n_items)
                pu[pu_indices] = 1.0

                ycy_reg = YtY + np.dot(self.Y.T, Cui.dot(self.Y)) + self.reg * np.eye(self.n_factors)
                Cu = Cui + sparse.eye(dataset.n_items, format="csr")
            #    print(Cu.toarray())
                cupu = Cu.dot(pu)
                ycp = np.dot(self.Y.T, cupu)
            #    ycp = Cu.dot(pu).T.dot(self.Y).flatten()
                self.X[u] = np.linalg.solve(ycy_reg, ycp)

            XtX = self.X.T.dot(self.X)
            for i in dataset.train_item:
                Cii_indices = list(dataset.train_item[i].keys())
                labels = list(dataset.train_item[i].values())
                Cii_values = np.array(labels) * self.alpha
                Cii = csr_matrix((Cii_values, (Cii_indices, Cii_indices)), shape=[dataset.n_users, dataset.n_users])

                pi_indices = list(dataset.train_item[i].keys())
                pi = np.zeros(dataset.n_users)
                pi[pi_indices] = 1.0

                xcx_reg = XtX + np.dot(self.X.T, Cii.dot(self.X)) + self.reg * np.eye(self.n_factors)
                Ci = Cii + sparse.eye(dataset.n_users, format="csr")
                cipi = Ci.dot(pi)
                xcp = np.dot(self.X.T, cipi)
                self.Y[i] = np.linalg.solve(xcx_reg, xcp)

            if verbose > 0 and epoch % 1 == 0 and self.task == "rating":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
                print("training rmse: ", rmse(self, dataset, "train"))
                print("test rmse: ", rmse(self, dataset, "test"))
            elif verbose > 0 and epoch % 1 == 0 and self.task == "ranking":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
            #    print("MAP@{}: {:.4f}".format(5, MAP_at_k(self, dataset, 5)))
                print("training accuracy: ", accuracy(self, dataset, "train"))
                print("test accuracy: ", accuracy(self, dataset, "test"))

        return self

    def predict(self, u, i):
        try:
            prob = 1 / (1 + np.exp(-np.dot(self.X[u], self.Y[i])))
            pred = 1.0 if prob >= 0.5 else 0.0
        except IndexError:
            pred = self.default_prediction
        return pred

    def recommend_user(self, u, n_rec, random_rec=False):
        unlabled_items = list(set(range(self.dataset.n_items)) - set(self.dataset.train_user[u]))
        if np.any(np.array(unlabled_items) > self.dataset.n_items):
            rank = [(j, self.predict(u, j)) for j in range(len(self.Y))
                    if j not in self.dataset.train_user[u]]
        else:
            pred = np.dot(self.X[u], self.Y[unlabled_items].T)
            pred = np.clip(pred, 1, 5)
            rank = list(zip(unlabled_items, pred))

        if random_rec:
            item_pred_dict = {j: r for j, r in rank if r >= 4}
            item_list = list(item_pred_dict.keys())
            pred_list = list(item_pred_dict.values())
            p = [p / np.sum(pred_list) for p in pred_list]
            item_candidates = np.random.choice(item_list, n_rec, replace=False, p=p)
            reco = [(item, item_pred_dict[item]) for item in item_candidates]
            return reco
        else:
            rank.sort(key=itemgetter(1), reverse=True)
            return rank[:n_rec]


class ALS_ranking:
    def __init__(self, n_factors=100, n_epochs=20, reg=5.0, task="rating", seed=42, alpha=10, cg_steps=3):
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.reg = reg
        self.task = task
        self.seed = seed
        self.alpha = alpha
        self.cg_steps = cg_steps

    @staticmethod
    def least_squares(dataset, X, Y, reg, n_factors, alpha=10, user=True):
        if user:
            data = dataset.train_user
        else:
            data = dataset.train_item

        YtY = Y.T.dot(Y)
        for s in data:
            A = YtY + reg * np.eye(n_factors)
            b = np.zeros(n_factors)
            for item, label in data[s].items():
                confidence = 1 + alpha * label
                factor = Y[item]
                A += (confidence - 1) * np.outer(factor, factor)
                b += confidence * factor
            X[s] = np.linalg.solve(A, b)

    @staticmethod
    def least_squares_cg(dataset, X, Y, reg, n_factors, alpha=10, cg_steps=3, user=True):
        if user:
            data = dataset.train_user
        else:
            data = dataset.train_item

        YtY = Y.T.dot(Y) + reg * np.eye(n_factors)
        for s in data:
            x = X[s]

            r = -YtY.dot(x)
            for item, label in data[s].items():
                confidence = 1 + alpha * label
                r += (confidence - (confidence - 1) * Y[item].dot(x)) * Y[item]

            p = r.copy()
            rs_old = r.dot(r)
            if rs_old < 1e-20:
                continue

            for it in range(cg_steps):
                Ap = YtY.dot(p)
                for item, label in data[s].items():
                    confidence = 1 + alpha * label
                    Ap += (confidence - 1) * Y[item].dot(p) * Y[item]

                # standard CG update
                alpha = rs_old / p.dot(Ap)
                x += alpha * p
                r -= alpha * Ap
                rs_new = r.dot(r)
                if rs_new < 1e-20:
                    break
                p = r + (rs_new / rs_old) * p
                rs_old = rs_new
            X[s] = x


    def fit(self, dataset, verbose=1, use_cg=True):
        np.random.seed(self.seed)
        self.dataset = dataset
        self.default_prediction = dataset.global_mean
        self.X = truncated_normal(shape=(dataset.n_users, self.n_factors),
                                   mean=0.0, scale=0.05)
        self.Y = truncated_normal(shape=(dataset.n_items, self.n_factors),
                                   mean=0.0, scale=0.05)
        if use_cg:
            method = functools.partial(ALS_ranking.least_squares_cg, cg_steps=self.cg_steps)
        else:
            method = ALS_ranking.least_squares

        for epoch in range(1, self.n_epochs + 1):
            t0 = time.time()
            method(self.dataset, self.X, self.Y, reg=self.reg,
                    n_factors=self.n_factors, alpha=self.alpha, user=True)

            method(self.dataset, self.Y, self.X, reg=self.reg,
                    n_factors=self.n_factors, alpha=self.alpha, user=False)

            if verbose > 0 and epoch % 1 == 0 and self.task == "rating":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
                print("training rmse: ", rmse(self, dataset, "train"))
                print("test rmse: ", rmse(self, dataset, "test"))
            elif verbose > 0 and epoch % 1 == 0 and self.task == "ranking":
                print("Epoch {} time: {:.4f}".format(epoch, time.time() - t0))
            #    print("MAP@{}: {:.4f}".format(5, MAP_at_k(self, dataset, 5)))
                print("training accuracy: ", accuracy(self, dataset, "train"))
                print("test accuracy: ", accuracy(self, dataset, "test"))

        return self

    def predict(self, u, i):
        try:
            prob = 1 / (1 + np.exp(-np.dot(self.X[u], self.Y[i])))
            pred = 1.0 if prob >= 0.5 else 0.0
        except IndexError:
            pred = self.default_prediction
        return pred





















