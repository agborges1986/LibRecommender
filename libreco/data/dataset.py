import itertools
import numpy as np
import pandas as pd

from .data_info import DataInfo
from .transformed import TransformedSet
from ..feature import (
    col_name2index,
    construct_unique_feat,
    get_user_item_sparse_indices,
    merge_sparse_indices,
    merge_sparse_col
)


class Dataset(object):
    """Base class for loading dataset.

    Warning: This class should not be used directly. Use derived class instead.
    """

    sparse_unique_vals = dict()
    multi_sparse_unique_vals = dict()
    user_unique_vals = None
    item_unique_vals = None
    dense_col = None
    sparse_col = None
    multi_sparse_col = None
    train_called = False

    @classmethod
    def load_builtin(cls, name="ml-1m") -> pd.DataFrame:
        pass

#    @classmethod
#    def load_from_file(cls, data, kind="pure"):
#        if kind == "pure":
#            return DatasetPure(data)
#        elif kind == "feat":
#            return DatasetFeat(data)
#        else:
#            raise ValueError("data kind must either be 'pure' or 'feat'.")

    @staticmethod
    def _check_col_names(data, mode):
        if not np.all(["user" == data.columns[0], "item" == data.columns[1]]):
            raise ValueError(
                "'user', 'item' must be the first two columns of the data"
            )
        if mode == "train":
            assert (
                "label" in data.columns,
                "train data should contain label column"
            )

    @classmethod
    def _check_subclass(cls):
        if not issubclass(cls, Dataset):
            raise NameError(
                "Please use 'DatasetPure' or 'DatasetFeat' to call method"
            )

    @classmethod
    def _set_feature_col(cls, sparse_col, dense_col, multi_sparse_col):
        cls.sparse_col = None if not sparse_col else sparse_col
        cls.dense_col = None if not dense_col else dense_col
        if multi_sparse_col:
            if not all(isinstance(field, list) for field in multi_sparse_col):
                cls.multi_sparse_col = [multi_sparse_col]
            else:
                cls.multi_sparse_col = multi_sparse_col

    @classmethod
    def _set_sparse_unique_vals(cls, train_data):
        if cls.sparse_col:
            for col in cls.sparse_col:
                cls.sparse_unique_vals[col] = np.unique(train_data[col])

        if cls.multi_sparse_col:
            for field in cls.multi_sparse_col:
                # use name of a field's first column as representative
                cls.multi_sparse_unique_vals[field[0]] = sorted(
                    set(
                        itertools.chain.from_iterable(
                            train_data[field].to_numpy().T)
                    )
                )

        cls.user_unique_vals = np.unique(train_data["user"])
        cls.item_unique_vals = np.unique(train_data["item"])


class DatasetPure(Dataset):
    """A derived class from :class:`Dataset`, used for pure
    collaborative filtering
    """

    @classmethod
    def build_trainset(cls, train_data, shuffle=False, seed=42):
        """Build transformed pure train_data from original data.

        Normally, pure data only contains `user` and `item` columns,
        so only `sparse_col` is needed.

        Parameters
        ----------
        train_data : `pandas.DataFrame`
            Data must at least contains three columns,
            i.e. `user`, `item`, `label`.
        shuffle : bool, optional
            Whether to fully shuffle data.
        seed: int, optional
            random seed.

        Returns
        -------
        trainset : `TransformedSet` object
            Data object used for training.
        data_info : `DataInfo` object
            Object that contains some useful information
            for training and predicting
        """

        cls._check_subclass()
        cls._check_col_names(train_data, mode="train")
        cls._set_sparse_unique_vals(train_data)
        if shuffle:
            train_data = train_data.sample(
                frac=1, random_state=seed
            ).reset_index(drop=True)

        user_indices, item_indices = get_user_item_sparse_indices(
            cls, train_data, mode="train"
        )
        labels = train_data["label"].to_numpy(dtype=np.float32)

        interaction_data = train_data[["user", "item", "label"]]
        train_transformed = TransformedSet(
            user_indices, item_indices, labels, train=True
        )

        data_info = DataInfo(interaction_data=interaction_data,
                             user_indices=user_indices,
                             item_indices=item_indices)
        return train_transformed, data_info

    @classmethod
    def build_evalset(cls, eval_data, shuffle=False, seed=42):
        return cls.build_testset(eval_data, shuffle, seed)

    @classmethod
    def build_testset(cls, test_data, shuffle=False, seed=42):
        """Build transformed pure eval_data or test_data from original data.

        Normally, pure data only contains `user` and `item` columns,
        so only `sparse_col` is needed.

        Parameters
        ----------
        test_data : `pandas.DataFrame`
            Data must at least contains two columns, i.e. `user`, `item`.
        shuffle : bool, optional
            Whether to fully shuffle data.
        seed: int, optional
            random seed.

        Returns
        -------
        testset : `TransformedSet` object
            Data object used for evaluate and test.
        """

        cls._check_subclass()
        cls._check_col_names(test_data, mode="test")
        if shuffle:
            test_data = test_data.sample(
                frac=1, random_state=seed
            ).reset_index(drop=True)

        test_user_indices, test_item_indices = get_user_item_sparse_indices(
            cls, test_data, mode="test"
        )
        if "label" in test_data.columns:
            labels = test_data["label"].to_numpy(dtype=np.float32)
        else:
            # in case test_data has no label column,
            # create dummy labels for consistency
            labels = np.zeros(len(test_data))

        test_transformed = TransformedSet(
            test_user_indices, test_item_indices, labels, train=False
        )
        return test_transformed

    @classmethod
    def build_train_test(cls, train_data, test_data,
                         shuffle=(False, False), seed=42):
        """Build transformed pure train_data and test_data from original data.

        Normally, pure data only contains `user` and `item` columns,
        so only `sparse_col` is needed.

        Parameters
        ----------
        train_data : `pandas.DataFrame`
            Data must at least contains three columns,
            i.e. `user`, `item`, `label`.
        test_data : `pandas.DataFrame`
            Data must at least contains two columns,
            i.e. `user`, `item`.
        shuffle : list of bool, optional
            Whether to fully shuffle train and test data
        seed: int, optional
            random seed

        Returns
        -------
        trainset : `TransformedSet` object
            Data object used for training.
        testset : `TransformedSet` object
            Data object used for evaluation and test.
        data_info : `DataInfo` object
            Object that contains some useful information for
            training and predicting
        """

        trainset, data_info = cls.build_trainset(train_data, shuffle[0], seed)
        testset = cls.build_testset(test_data, shuffle[1], seed)
        return trainset, testset, data_info


class DatasetFeat(Dataset):
    """A derived class from :class:`Dataset`, used for data that
    contains features
    """

    @classmethod   # TODO: pseudo pure
    def build_trainset(cls, train_data, user_col=None, item_col=None,
                       sparse_col=None, dense_col=None, multi_sparse_col=None,
                       shuffle=False, seed=42):
        """Build transformed feat train_data from original data.

        Normally, `user` and `item` column will be transformed into
        sparse indices, so `sparse_col` must be provided.

        Parameters
        ----------
        train_data : `pandas.DataFrame`
            Data must at least contains three columns,
            i.e. `user`, `item`, `label`.
        user_col : list of str
            List of user feature column names.
        item_col : list of str
            List of item feature column names.
        sparse_col : list of str
            List of sparse feature columns names.
        multi_sparse_col : list of list of str
            List of list of multi_sparse feature columns names.
            For example, [["a", "b", "c"], ["d", "e"]]
        dense_col : list of str, optional
            List of dense feature column names.
        shuffle : bool, optional
            Whether to fully shuffle data.
        seed: int, optional
            random seed.

        Returns
        -------
        trainset : `TransformedSet` object
            Data object used for training.
        data_info : `DataInfo` object
            Object that contains some useful information
            for training and predicting
        """

        cls._check_subclass()
        cls._check_col_names(train_data, mode="train")
        cls._set_feature_col(sparse_col, dense_col, multi_sparse_col)
        cls._set_sparse_unique_vals(train_data)
        if shuffle:
            train_data = train_data.sample(
                frac=1, random_state=seed
            ).reset_index(drop=True)

        user_indices, item_indices = get_user_item_sparse_indices(
            cls, train_data, mode="train"
        )
        train_sparse_indices = (
            merge_sparse_indices(
                cls, train_data, cls.sparse_col,
                cls.multi_sparse_col, mode="train"
            )
            if cls.sparse_col or cls.multi_sparse_col
            else None
        )
        train_dense_values = (
            train_data[cls.dense_col].to_numpy()
            if cls.dense_col
            else None
        )
        labels = train_data["label"].to_numpy(dtype=np.float32)

        train_transformed = TransformedSet(user_indices,
                                           item_indices,
                                           labels,
                                           train_sparse_indices,
                                           train_dense_values,
                                           train=True)

    #    if cls.multi_sparse_col:
    #        cls.sparse_col = merge_sparse_col(cls.sparse_col,
    #                                          cls.multi_sparse_col)

        all_sparse_col = (
            merge_sparse_col(cls.sparse_col, cls.multi_sparse_col)
            if cls.multi_sparse_col
            else sparse_col
        )
        col_name_mapping = col_name2index(
            user_col, item_col, all_sparse_col, cls.dense_col
        )
        user_sparse_col_indices = list(
            col_name_mapping["user_sparse_col"].values()
        )
        user_dense_col_indices = list(
            col_name_mapping["user_dense_col"].values()
        )
        item_sparse_col_indices = list(
            col_name_mapping["item_sparse_col"].values()
        )
        item_dense_col_indices = list(
            col_name_mapping["item_dense_col"].values()
        )

        (
            user_sparse_unique,
            user_dense_unique,
            item_sparse_unique,
            item_dense_unique
        ) = construct_unique_feat(
            user_indices,
            item_indices,
            train_sparse_indices,
            train_dense_values,
            user_sparse_col_indices,
            user_dense_col_indices,
            item_sparse_col_indices,
            item_dense_col_indices
        )

        interaction_data = train_data[["user", "item", "label"]]
        data_info = DataInfo(col_name_mapping,
                             interaction_data,
                             user_sparse_unique,
                             user_dense_unique,
                             item_sparse_unique,
                             item_dense_unique,
                             user_indices,
                             item_indices)

        cls.train_called = True
        return train_transformed, data_info

    @classmethod
    def build_evalset(cls, eval_data, shuffle=False, seed=42):

        return cls.build_testset(eval_data, shuffle, seed)

    @classmethod
    def build_testset(cls, test_data, shuffle=False, seed=42):
        """Build transformed feat eval_data or test_data from original data.

        Normally, `user` and `item` column will be transformed
        into sparse indices, so `sparse_col` must be provided.

        Parameters
        ----------
        test_data : `pandas.DataFrame`
            Data must at least contains two columns, i.e. `user`, `item`.
        shuffle : bool, optional
            Whether to fully shuffle data.
        seed: int, optional
            random seed.

        Returns
        -------
        testset : `TransformedSet` object
            Data object used for evaluation and test.
        """

        if not cls.train_called:
            raise RuntimeError(
                "must first build trainset before building evalset or testset"
            )
        cls._check_subclass()
        cls._check_col_names(test_data, "test")
        if shuffle:
            test_data = test_data.sample(
                frac=1, random_state=seed
            ).reset_index(drop=True)

        (
            test_user_indices,
            test_item_indices
        ) = get_user_item_sparse_indices(cls, test_data, mode="test")
        test_sparse_indices = (
            merge_sparse_indices(
                cls, test_data, cls.sparse_col,
                cls.multi_sparse_col, mode="test"
            )
            if cls.sparse_col or cls.multi_sparse_col
            else None
        )
        test_dense_values = (
            test_data[cls.dense_col].to_numpy() if cls.dense_col else None
        )

        if "label" in test_data.columns:
            labels = test_data["label"].to_numpy(dtype=np.float32)
        else:
            # in case test_data has no label column,
            # create dummy labels for consistency
            labels = np.zeros(len(test_data), dtype=np.float32)

        test_transformed = TransformedSet(test_user_indices,
                                          test_item_indices,
                                          labels,
                                          test_sparse_indices,
                                          test_dense_values,
                                          train=False)

        return test_transformed

    @classmethod
    def build_train_test(cls, train_data, test_data, user_col=None,
                         item_col=None, sparse_col=None, dense_col=None,
                         multi_sparse_col=None, shuffle=(False, False),
                         seed=42):
        """Build transformed feat train_data and test_data from original data.

        Normally, `user` and `item` column will be transformed into
        sparse indices, so `sparse_col` must be provided.

        Parameters
        ----------
        train_data : `pandas.DataFrame`
            Data must at least contains three columns,
            i.e. `user`, `item`, `label`.
        test_data : `pandas.DataFrame`
            Data must at least contains two columns,
            i.e. `user`, `item`.
        user_col : list of str
            List of user feature column names.
        item_col : list of str
            List of item feature column names.
        sparse_col : list of str
            List of sparse feature columns names,
            usually include `user` and `item`, so it must be provided.
        dense_col : list of str, optional
            List of dense feature column names.
        multi_sparse_col : list of list of str
            List of list of multi_sparse feature columns names.
            For example, [["a", "b", "c"], ["d", "e"]]
        shuffle : list of bool, optional
            Whether to fully shuffle data.
        seed: int, optional
            random seed.

        Returns
        -------
        trainset : `TransformedSet` object
            Data object used for training.
        testset : `TransformedSet` object
            Data object used for evaluation and test.
        data_info : `DataInfo` object
            Object that contains some useful information
            for training and predicting
        """
        trainset, data_info = cls.build_trainset(
            train_data, user_col, item_col, sparse_col,
            dense_col, multi_sparse_col, shuffle[0], seed
        )
        testset = cls.build_testset(test_data, shuffle[1], seed)
        return trainset, testset, data_info
